"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  deleteAdminUser,
  getAdminUsers,
  updateAdminUser,
  type AdminUser,
} from "@/lib/api/admin";
import { ApiError } from "@/lib/api/client";

type UserDraft = {
  username: string;
  email: string;
  isAdmin: boolean;
  password: string;
};

type UserStatus = {
  isFading: boolean;
  message: string;
  type: "error" | "success";
};

type UserStatusTimers = {
  fade: number;
  remove: number;
};

const inputClassName =
  "h-10 w-full rounded-md border border-home-surface bg-home-background px-3 text-sm text-home-text outline-none transition placeholder:text-home-muted focus:border-home-accent";

function createUserDraft(user: AdminUser): UserDraft {
  return {
    username: user.username,
    email: user.email,
    isAdmin: user.is_admin === 1,
    password: "",
  };
}

function formatCreatedAt(createdAt: string) {
  return createdAt.replace("T", " ").slice(0, 19);
}

export default function AdminUsersTable() {
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [drafts, setDrafts] = useState<Record<number, UserDraft>>({});
  const [statuses, setStatuses] = useState<Record<number, UserStatus>>({});
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [savingUserId, setSavingUserId] = useState<number | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);
  const statusTimers = useRef<Record<number, UserStatusTimers>>({});

  useEffect(() => {
    let isActive = true;

    getAdminUsers()
      .then((response) => {
        if (!isActive) {
          return;
        }

        const nextDrafts: Record<number, UserDraft> = {};

        response.users.forEach((user) => {
          nextDrafts[user.id] = createUserDraft(user);
        });

        setUsers(response.users);
        setDrafts(nextDrafts);
      })
      .catch((error) => {
        if (!isActive) {
          return;
        }

        if (error instanceof ApiError && error.status === 401) {
          router.replace("/login?next=/admin");
          return;
        }

        if (error instanceof ApiError && error.status === 403) {
          router.replace("/");
          return;
        }

        setErrorMessage(
          error instanceof Error ? error.message : "Unable to load users",
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
  }, [router]);

  useEffect(() => {
    const timersByUser = statusTimers.current;

    return () => {
      Object.values(timersByUser).forEach((timers) => {
        window.clearTimeout(timers.fade);
        window.clearTimeout(timers.remove);
      });
    };
  }, []);

  function clearUserStatusTimers(userId: number) {
    const timers = statusTimers.current[userId];

    if (!timers) {
      return;
    }

    window.clearTimeout(timers.fade);
    window.clearTimeout(timers.remove);
    delete statusTimers.current[userId];
  }

  function showTemporarySuccess(userId: number, message: string) {
    clearUserStatusTimers(userId);
    setStatuses((current) => ({
      ...current,
      [userId]: {
        isFading: false,
        message,
        type: "success",
      },
    }));

    statusTimers.current[userId] = {
      fade: window.setTimeout(() => {
        setStatuses((current) => {
          const status = current[userId];

          if (!status || status.type !== "success") {
            return current;
          }

          return {
            ...current,
            [userId]: {
              ...status,
              isFading: true,
            },
          };
        });
      }, 2500),
      remove: window.setTimeout(() => {
        setStatuses((current) => {
          const nextStatuses = { ...current };
          delete nextStatuses[userId];
          return nextStatuses;
        });
        delete statusTimers.current[userId];
      }, 3000),
    };
  }

  function updateDraft(
    userId: number,
    field: keyof UserDraft,
    value: string | boolean,
  ) {
    clearUserStatusTimers(userId);
    setDrafts((current) => ({
      ...current,
      [userId]: {
        ...current[userId],
        [field]: value,
      },
    }));

    setStatuses((current) => {
      const nextStatuses = { ...current };
      delete nextStatuses[userId];
      return nextStatuses;
    });
  }

  async function handleSave(
    event: FormEvent<HTMLFormElement>,
    userId: number,
  ) {
    event.preventDefault();

    const draft = drafts[userId];

    if (!draft) {
      return;
    }

    setSavingUserId(userId);
    clearUserStatusTimers(userId);
    setStatuses((current) => {
      const nextStatuses = { ...current };
      delete nextStatuses[userId];
      return nextStatuses;
    });

    try {
      const response = await updateAdminUser(userId, draft);

      setUsers((current) =>
        current.map((user) =>
          user.id === userId ? response.user : user,
        ),
      );
      setDrafts((current) => ({
        ...current,
        [userId]: createUserDraft(response.user),
      }));
      showTemporarySuccess(userId, response.message);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/login?next=/admin");
        return;
      }

      if (error instanceof ApiError && error.status === 403) {
        router.replace("/");
        return;
      }

      setStatuses((current) => ({
        ...current,
        [userId]: {
          isFading: false,
          message:
            error instanceof Error ? error.message : "Unable to update user",
          type: "error",
        },
      }));
    } finally {
      setSavingUserId(null);
    }
  }

  async function handleDelete(user: AdminUser) {
    const confirmed = window.confirm(
      `Delete the account for ${user.username}? This cannot be undone.`,
    );

    if (!confirmed) {
      return;
    }

    setDeletingUserId(user.id);
    clearUserStatusTimers(user.id);
    setStatuses((current) => {
      const nextStatuses = { ...current };
      delete nextStatuses[user.id];
      return nextStatuses;
    });

    try {
      await deleteAdminUser(user.id);

      setUsers((current) =>
        current.filter((currentUser) => currentUser.id !== user.id),
      );
      setDrafts((current) => {
        const nextDrafts = { ...current };
        delete nextDrafts[user.id];
        return nextDrafts;
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/login?next=/admin");
        return;
      }

      if (error instanceof ApiError && error.status === 403) {
        router.replace("/");
        return;
      }

      setStatuses((current) => ({
        ...current,
        [user.id]: {
          isFading: false,
          message:
            error instanceof Error ? error.message : "Unable to delete user",
          type: "error",
        },
      }));
    } finally {
      setDeletingUserId(null);
    }
  }

  if (isLoading) {
    return <p className="text-sm text-home-muted">Loading users...</p>;
  }

  if (errorMessage) {
    return <p className="text-sm text-home-muted">{errorMessage}</p>;
  }

  if (users.length === 0) {
    return <p className="text-sm text-home-muted">No users found.</p>;
  }

  return (
    <section aria-labelledby="user-management-title">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2
            id="user-management-title"
            className="text-lg font-semibold sm:text-xl"
          >
            User Management
          </h2>
          <p className="mt-1 text-sm text-home-muted">
            Edit account details or enter a new password to replace the current
            one.
          </p>
        </div>
        <span className="shrink-0 text-sm text-home-muted">
          {users.length} {users.length === 1 ? "user" : "users"}
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-home-surface">
        <table className="w-full min-w-5xl border-collapse text-left">
          <thead className="bg-home-surface/80 text-xs uppercase tracking-wide text-home-muted">
            <tr>
              <th className="px-3 py-3 font-semibold">ID</th>
              <th className="px-3 py-3 font-semibold">Username</th>
              <th className="px-3 py-3 font-semibold">Email</th>
              <th className="px-3 py-3 font-semibold">New password</th>
              <th className="px-3 py-3 font-semibold">Admin</th>
              <th className="py-3 pr-1 pl-3 font-semibold">Created</th>
              <th className="py-3 pr-3 pl-1 text-center font-semibold">
                <span className="inline-block -translate-x-2">
                  Episodes Completed
                </span>
              </th>
              <th className="px-3 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-home-surface">
            {users.map((user) => {
              const draft = drafts[user.id];

              if (!draft) {
                return null;
              }

              const formId = `edit-user-${user.id}`;
              const status = statuses[user.id];
              const isSaving = savingUserId === user.id;
              const isDeleting = deletingUserId === user.id;

              return (
                <tr className="bg-home-background align-middle" key={user.id}>
                  <td className="px-3 py-4 text-sm text-home-muted">
                    {user.id}
                  </td>
                  <td className="w-48 px-3 py-4">
                    <input
                      aria-label={`Username for user ${user.id}`}
                      className={inputClassName}
                      form={formId}
                      maxLength={50}
                      name="username"
                      onChange={(event) =>
                        updateDraft(user.id, "username", event.target.value)
                      }
                      required
                      type="text"
                      value={draft.username}
                    />
                  </td>
                  <td className="w-64 px-3 py-4">
                    <input
                      aria-label={`Email for user ${user.id}`}
                      className={inputClassName}
                      form={formId}
                      maxLength={254}
                      name="email"
                      onChange={(event) =>
                        updateDraft(user.id, "email", event.target.value)
                      }
                      required
                      type="email"
                      value={draft.email}
                    />
                  </td>
                  <td className="w-56 px-3 py-4">
                    <input
                      aria-label={`New password for user ${user.id}`}
                      autoComplete="new-password"
                      className={inputClassName}
                      form={formId}
                      maxLength={72}
                      name="password"
                      onChange={(event) =>
                        updateDraft(user.id, "password", event.target.value)
                      }
                      placeholder="Leave unchanged"
                      type="password"
                      value={draft.password}
                    />
                  </td>
                  <td className="px-3 py-4">
                    <label className="flex h-10 items-center gap-2 whitespace-nowrap text-sm">
                      <input
                        aria-label={`Admin access for user ${user.id}`}
                        checked={draft.isAdmin}
                        className="size-4 accent-home-accent"
                        form={formId}
                        name="is_admin"
                        onChange={(event) =>
                          updateDraft(
                            user.id,
                            "isAdmin",
                            event.target.checked,
                          )
                        }
                        type="checkbox"
                      />
                      Admin
                    </label>
                  </td>
                  <td className="py-4 pr-1 pl-3 text-sm whitespace-nowrap text-home-muted">
                    {formatCreatedAt(user.created_at)}
                  </td>
                  <td className="py-4 pr-3 pl-1 text-center text-sm font-semibold text-home-text">
                    <span className="inline-block -translate-x-2">
                      {user.episodes_completed}
                    </span>
                  </td>
                  <td className="relative w-56 px-3 py-4">
                    <form
                      className="relative flex h-10 items-center justify-center"
                      id={formId}
                      onSubmit={(event) => handleSave(event, user.id)}
                    >
                      <div className="flex justify-center gap-2">
                        <button
                          className="h-10 rounded-md bg-home-text px-4 text-sm font-semibold text-home-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={
                            savingUserId !== null || deletingUserId !== null
                          }
                          type="submit"
                        >
                          {isSaving ? "Saving..." : "Save"}
                        </button>
                        <button
                          className="h-10 rounded-md border border-home-danger/70 px-3 text-sm font-semibold text-home-muted transition hover:border-home-danger hover:bg-home-danger/5 hover:text-home-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-home-danger/70 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={
                            savingUserId !== null || deletingUserId !== null
                          }
                          onClick={() => handleDelete(user)}
                          type="button"
                        >
                          {isDeleting ? "Deleting..." : "Delete"}
                        </button>
                      </div>
                      {status && (
                        <p
                          aria-live="polite"
                          className={`absolute top-full left-1/2 mt-1 -translate-x-1/2 whitespace-nowrap text-xs transition-opacity duration-500 ${
                            status.isFading ? "opacity-0" : "opacity-100"
                          } ${
                            status.type === "success"
                              ? "text-home-accent"
                              : "text-home-muted"
                          }`}
                        >
                          {status.message}
                        </p>
                      )}
                    </form>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
