"use client";

import { useMe } from "./session-context";

export interface EntityOwnership {
  isMine: boolean;
  ownerName: string | null;
  ownerId: string | null;
}

type Idish = string | number | null | undefined;
interface Person {
  id?: Idish;
  name?: string | null;
}

/**
 * Anything that can belong to a person: an account, an action card (assignee), a finding (via
 * its account). The API uses a few spellings for the same idea, so all of them are read here.
 */
export interface Ownable {
  owner_user_id?: Idish;
  owner_id?: Idish;
  owner?: Person | null;
  owner_name?: string | null;
  assignee_user_id?: Idish;
  assignee_id?: Idish;
  assignee?: Person | null;
  assignee_name?: string | null;
  account?: {
    owner_user_id?: Idish;
    owner_id?: Idish;
    owner?: Person | null;
    owner_name?: string | null;
  } | null;
}

type CurrentUserInput = string | null | undefined | { user?: { id?: Idish } | null; user_id?: Idish };

const first = (...values: Idish[]): string | null => {
  for (const v of values) if (v !== null && v !== undefined && v !== "") return String(v);
  return null;
};

/**
 * "Mine" means the entity's owner or assignee is the signed-in user, by id. Never by name:
 * display names are not identities.
 */
export function checkEntityOwnership(
  entity: Ownable | null | undefined,
  currentUser?: CurrentUserInput,
  _activeRole?: string
): EntityOwnership {
  if (!entity) return { isMine: false, ownerName: null, ownerId: null };

  const currentUserId =
    typeof currentUser === "object" && currentUser !== null
      ? first(currentUser.user?.id, currentUser.user_id)
      : first(currentUser);

  const ownerId = first(
    entity.owner_user_id,
    entity.owner_id,
    entity.owner?.id,
    entity.assignee_user_id,
    entity.assignee_id,
    entity.assignee?.id,
    entity.account?.owner_user_id,
    entity.account?.owner?.id,
    entity.account?.owner_id
  );

  const ownerName =
    entity.owner?.name ??
    entity.owner_name ??
    entity.assignee?.name ??
    entity.assignee_name ??
    entity.account?.owner?.name ??
    entity.account?.owner_name ??
    null;

  if (currentUserId && ownerId && ownerId === currentUserId) {
    return { isMine: true, ownerName, ownerId };
  }

  return {
    isMine: false,
    ownerName: ownerName ?? (ownerId ? `User ${ownerId.slice(0, 8)}` : null),
    ownerId,
  };
}

/** Hook to check if an entity belongs to the current user. */
export function useIsMine(entity: Ownable | null | undefined): boolean {
  const { me } = useMe();
  return checkEntityOwnership(entity, me?.user?.id).isMine;
}

/** Hook to retrieve full ownership info (isMine, ownerName, ownerId) for an entity. */
export function useEntityOwnership(entity: Ownable | null | undefined): EntityOwnership {
  const { me } = useMe();
  return checkEntityOwnership(entity, me?.user?.id);
}
