import { requestWithSessionRefresh } from "@/lib/api/auth";
import { apiRequest } from "@/lib/api/client";

export type EpisodeComment = {
  id: number;
  user_id: number;
  username: string;
  episode_id: number;
  comment_text: string;
  parent_id: number | null;
  created_at: string;
};

type CommentsResponse = {
  comments: EpisodeComment[];
  pagination: {
    count: number;
    has_more: boolean;
    limit: number;
    offset: number;
  };
};

type CommentResponse = {
  message: string;
  comment: EpisodeComment;
};

type CommentActionResponse = {
  message: string;
};

function requestEpisodeComments(
  slug: string,
  episodeNumber: number,
  limit: number,
  offset: number,
) {
  return apiRequest<CommentsResponse>(
    `/api/anime/${encodeURIComponent(slug)}/episodes/${episodeNumber}/comments?limit=${limit}&offset=${offset}`,
  );
}

export function getEpisodeComments(
  slug: string,
  episodeNumber: number,
  limit = 20,
  offset = 0,
) {
  return requestWithSessionRefresh(() =>
    requestEpisodeComments(slug, episodeNumber, limit, offset),
  );
}

function requestCreateEpisodeComment(
  slug: string,
  episodeNumber: number,
  commentText: string,
  parentId: number | null,
) {
  return apiRequest<CommentResponse>(
    `/api/anime/${encodeURIComponent(slug)}/episodes/${episodeNumber}/comments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        comment_text: commentText,
        parent_id: parentId,
      }),
      csrf: "access",
    },
  );
}

export function createEpisodeComment(
  slug: string,
  episodeNumber: number,
  commentText: string,
  parentId: number | null = null,
) {
  return requestWithSessionRefresh(() =>
    requestCreateEpisodeComment(
      slug,
      episodeNumber,
      commentText,
      parentId,
    ),
  );
}

function requestEditEpisodeComment(commentId: number, commentText: string) {
  return apiRequest<CommentResponse>(`/api/comments/${commentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comment_text: commentText }),
    csrf: "access",
  });
}

export function editEpisodeComment(
  commentId: number,
  commentText: string,
) {
  return requestWithSessionRefresh(() =>
    requestEditEpisodeComment(commentId, commentText),
  );
}

function requestDeleteEpisodeComment(commentId: number) {
  return apiRequest<CommentActionResponse>(`/api/comments/${commentId}`, {
    method: "DELETE",
    csrf: "access",
  });
}

export function deleteEpisodeComment(commentId: number) {
  return requestWithSessionRefresh(() =>
    requestDeleteEpisodeComment(commentId),
  );
}
