import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router";

import { useSearch } from "../api/queries";
import { ItemRow } from "../components/ItemRow";
import { ListDetail } from "../components/ListDetail";
import { Empty, ScreenHeader } from "../components/ui";

export function SearchScreen() {
  const { itemId } = useParams();
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const suffix = q ? `?q=${encodeURIComponent(q)}` : "";
  return (
    <ListDetail
      itemId={itemId}
      back={{ to: `/search${suffix}`, label: "Search" }}
      list={<SearchList selectedId={itemId} />}
    />
  );
}

/** Words in the title, across the inbox and every project. The query lives in the URL,
 *  so going into an item and back keeps it. */
function SearchList({ selectedId }: { selectedId?: string }) {
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [q, setQ] = useState(text);
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(text.trim());
      setParams(text.trim() ? { q: text.trim() } : {}, { replace: true });
    }, 200);
    return () => clearTimeout(t);
  }, [text, setParams]);
  const results = useSearch(q);
  const suffix = q ? `?q=${encodeURIComponent(q)}` : "";

  return (
    <>
      <ScreenHeader title="Search" />
      <div className="border-hairline border-b px-5 py-4 lg:px-7">
        <label htmlFor="search" className="sr-only">
          Search items
        </label>
        <input
          id="search"
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Words in the title"
          autoComplete="off"
          className="border-rule bg-surface text-text focus:border-accent h-12 w-full border-2 px-3.5 text-[17px] outline-none"
        />
      </div>
      {!q ? null : results.data?.length === 0 ? (
        <Empty>No item has all of these words in its title.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {(results.data ?? []).map((hit) => (
            <li key={hit.id}>
              <ItemRow
                item={hit}
                to={`/search/${hit.id}${suffix}`}
                selected={hit.id === selectedId}
                meta={hit.project_name ?? "Inbox"}
              />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
