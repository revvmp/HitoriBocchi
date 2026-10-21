"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import {
  getOptionalCurrentUser,
  type CurrentUser,
} from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import {
  createEpisodeComment,
  deleteEpisodeComment,
  editEpisodeComment,
  getEpisodeComments,
  type EpisodeComment,
} from "@/lib/api/comments";

type EpisodeCommentsProps = {
  slug: string;
  episodeNumber: number;
};

function formatCommentDate(createdAt: string) {
  const normalizedDate = createdAt.includes("T")
    ? createdAt
    : `${createdAt.replace(" ", "T")}Z`;
  const date = new Date(normalizedDate);

  if (Number.isNaN(date.getTime())) {
    return createdAt;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function EpisodeComments({
  slug,
  episodeNumber,
}: EpisodeCommentsProps) {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [comments, setComments] = useState<EpisodeComment[]>([]);
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [replyingTo, setReplyingTo] = useState<EpisodeComment | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [activeCommentId, setActiveCommentId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isPosting, setIsPosting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isActive = true;

    Promise.all([
      getOptionalCurrentUser(),
      getEpisodeComments(slug, episodeNumber),
    ])
      .then(([currentUser, commentsResponse]) => {
        if (!isActive) {
          return;
        }

        setCurrentUser(currentUser);
        setComments(commentsResponse.comments);
        setNextOffset(commentsResponse.pagination.count);
        setHasMore(commentsResponse.pagination.has_more);
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }

        if (
          error instanceof ApiError &&
          [401, 403].includes(error.status)
        ) {
          router.replace("/login");
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load comments",
        );
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [episodeNumber, router, slug]);

  async function handleCreateComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedComment = commentText.trim();

    if (!trimmedComment) {
      return;
    }

    setIsPosting(true);
    setErrorMessage("");

    try {
      const response = await createEpisodeComment(
        slug,
        episodeNumber,
        trimmedComment,
        replyingTo?.id ?? null,
      );

      setComments((currentComments) => [
        ...currentComments,
        response.comment,
      ]);
      setCommentText("");
      setReplyingTo(null);

      if (!hasMore) {
        setNextOffset((currentOffset) => currentOffset + 1);
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to post comment",
      );
    } finally {
      setIsPosting(false);
    }
  }

  async function handleLoadMore() {
    setIsLoadingMore(true);
    setErrorMessage("");

    try {
      const response = await getEpisodeComments(
        slug,
        episodeNumber,
        20,
        nextOffset,
      );

      setComments((currentComments) => {
        const existingIds = new Set(
          currentComments.map((comment) => comment.id),
        );
        const newComments = response.comments.filter(
          (comment) => !existingIds.has(comment.id),
        );

        return [...currentComments, ...newComments];
      });
      setNextOffset(
        response.pagination.offset + response.pagination.count,
      );
      setHasMore(response.pagination.has_more);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to load comments",
      );
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleEditComment(
    event: FormEvent<HTMLFormElement>,
    commentId: number,
  ) {
    event.preventDefault();

    const trimmedComment = editingText.trim();

    if (!trimmedComment) {
      return;
    }

    setActiveCommentId(commentId);
    setErrorMessage("");

    try {
      const response = await editEpisodeComment(commentId, trimmedComment);

      setComments((currentComments) =>
        currentComments.map((comment) =>
          comment.id === commentId ? response.comment : comment,
        ),
      );
      setEditingId(null);
      setEditingText("");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to edit comment",
      );
    } finally {
      setActiveCommentId(null);
    }
  }

  async function handleDeleteComment(commentId: number) {
    if (!window.confirm("Delete this comment?")) {
      return;
    }

    setActiveCommentId(commentId);
    setErrorMessage("");

    try {
      await deleteEpisodeComment(commentId);
      setComments((currentComments) =>
        currentComments.filter(
          (comment) =>
            comment.id !== commentId && comment.parent_id !== commentId,
        ),
      );
      setNextOffset((currentOffset) => Math.max(0, currentOffset - 1));
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to delete comment",
      );
    } finally {
      setActiveCommentId(null);
    }
  }

  const commentUsers = new Map(
    comments.map((comment) => [comment.id, comment.username]),
  );

  return (
    <section
      className="mt-10 border-t border-home-surface pt-7"
      aria-labelledby="comments-title"
    >
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 id="comments-title" className="text-xl font-semibold">
            Comments
          </h2>
          <p className="mt-1 text-sm text-home-muted">
            Discuss this episode with other users!
          </p>
        </div>
        <span className="text-sm text-home-muted">
          {comments.length} loaded
        </span>
      </div>

      {!isLoading && (currentUser ? (
        <form
          className="mt-5 rounded-lg border border-home-surface bg-home-surface/30 p-4"
          onSubmit={handleCreateComment}
        >
          {replyingTo && (
            <div className="mb-3 flex items-center justify-between gap-3 text-sm text-home-muted">
              <span>Replying to {replyingTo.username}</span>
              <button
                className="font-semibold text-home-accent"
                type="button"
                onClick={() => setReplyingTo(null)}
              >
                Cancel reply
              </button>
            </div>
          )}
          <label className="sr-only" htmlFor="episode-comment">
            Add a comment
          </label>
          <textarea
            className="min-h-24 w-full resize-y rounded-md border border-home-surface bg-home-background px-3 py-2 text-sm text-home-text outline-none placeholder:text-home-muted focus:border-home-accent"
            id="episode-comment"
            maxLength={2000}
            placeholder="Leave a comment."
            required
            value={commentText}
            onChange={(event) => setCommentText(event.target.value)}
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-xs text-home-muted">
              {commentText.length}/2000
            </span>
            <button
              className="rounded-md bg-home-accent px-4 py-2 text-sm font-semibold text-home-background transition hover:opacity-90 disabled:opacity-60"
              disabled={isPosting || !commentText.trim()}
              type="submit"
            >
              {isPosting
                ? "Posting..."
                : replyingTo
                  ? "Post reply"
                  : "Post comment"}
            </button>
          </div>
        </form>
      ) : (
        <p className="mt-5 rounded-lg border border-home-surface bg-home-surface/30 p-4 text-sm text-home-muted">
          Comments are read-only without an account.
        </p>
      ))}

      {errorMessage && (
        <p className="mt-4 text-sm text-home-text" role="alert">
          {errorMessage}
        </p>
      )}

      {isLoading ? (
        <div className="mt-6 space-y-3 animate-pulse">
          <div className="h-24 rounded-lg bg-home-surface/50" />
          <div className="h-24 rounded-lg bg-home-surface/50" />
        </div>
      ) : comments.length === 0 ? (
        <p className="mt-6 text-sm text-home-muted">
          {currentUser
            ? "No comments yet. Be the first to comment."
            : "No comments yet."}
        </p>
      ) : (
        <div className="mt-6 space-y-3">
          {comments.map((comment) => {
            const isOwner = currentUser?.id === comment.user_id;
            const canDelete = isOwner || currentUser?.is_admin === 1;
            const isEditing = editingId === comment.id;
            const parentUsername = comment.parent_id
              ? commentUsers.get(comment.parent_id)
              : null;

            return (
              <article
                className={`rounded-lg border border-home-surface bg-home-surface/30 p-4 ${
                  comment.parent_id ? "ml-4 sm:ml-8" : ""
                }`}
                key={comment.id}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-home-text">
                      {comment.username}
                    </p>
                    <p className="mt-0.5 text-xs text-home-muted">
                      {formatCommentDate(comment.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-xs font-semibold">
                    {currentUser && (
                      <button
                        className="text-home-accent"
                        type="button"
                        onClick={() => setReplyingTo(comment)}
                      >
                        Reply
                      </button>
                    )}
                    {isOwner && !isEditing && (
                      <button
                        className="text-home-muted hover:text-home-text"
                        type="button"
                        onClick={() => {
                          setEditingId(comment.id);
                          setEditingText(comment.comment_text);
                        }}
                      >
                        Edit
                      </button>
                    )}
                    {canDelete && (
                      <button
                        className="text-home-muted hover:text-home-text disabled:opacity-60"
                        disabled={activeCommentId === comment.id}
                        type="button"
                        onClick={() => handleDeleteComment(comment.id)}
                      >
                        {activeCommentId === comment.id
                          ? "Deleting..."
                          : "Delete"}
                      </button>
                    )}
                  </div>
                </div>

                {parentUsername && (
                  <p className="mt-3 text-xs text-home-muted">
                    Reply to {parentUsername}
                  </p>
                )}

                {isEditing ? (
                  <form
                    className="mt-3"
                    onSubmit={(event) =>
                      handleEditComment(event, comment.id)
                    }
                  >
                    <label
                      className="sr-only"
                      htmlFor={`edit-comment-${comment.id}`}
                    >
                      Edit comment
                    </label>
                    <textarea
                      className="min-h-20 w-full resize-y rounded-md border border-home-surface bg-home-background px-3 py-2 text-sm text-home-text outline-none focus:border-home-accent"
                      id={`edit-comment-${comment.id}`}
                      maxLength={2000}
                      required
                      value={editingText}
                      onChange={(event) => setEditingText(event.target.value)}
                    />
                    <div className="mt-2 flex justify-end gap-2">
                      <button
                        className="rounded-md px-3 py-1.5 text-xs font-semibold text-home-muted hover:text-home-text"
                        type="button"
                        onClick={() => {
                          setEditingId(null);
                          setEditingText("");
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        className="rounded-md bg-home-accent px-3 py-1.5 text-xs font-semibold text-home-background disabled:opacity-60"
                        disabled={
                          activeCommentId === comment.id ||
                          !editingText.trim()
                        }
                        type="submit"
                      >
                        {activeCommentId === comment.id
                          ? "Saving..."
                          : "Save"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-home-text">
                    {comment.comment_text}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}

      {hasMore && (
        <div className="mt-5 text-center">
          <button
            className="rounded-md border border-home-surface px-4 py-2 text-sm font-semibold text-home-text transition hover:border-home-accent disabled:opacity-60"
            disabled={isLoadingMore}
            type="button"
            onClick={handleLoadMore}
          >
            {isLoadingMore ? "Loading..." : "Load more comments"}
          </button>
        </div>
      )}
    </section>
  );
}
