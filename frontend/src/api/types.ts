import type { components } from "./schema";

type S = components["schemas"];

export type Project = S["ProjectOut"];
export type ProjectState = Project["state"];
export type Item = S["ItemOut"];
export type ItemStatus = Item["status"];
export type ItemDetail = S["ItemDetail"];
export type Activity = S["ActivityOut"];
export type SearchHit = S["SearchHit"];
