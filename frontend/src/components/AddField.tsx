import { useState, type FormEvent } from "react";

import { Button, TextBox } from "./ui";

/** "+ Add to …": a title, and once there is one, optional details and an Add button.
 *  Return in the title adds at once (DECISIONS #87). */
export function AddField({
  id,
  label,
  placeholder,
  onAdd,
}: {
  id: string;
  label: string;
  placeholder: string;
  onAdd: (item: { title: string; details: string }) => void;
}) {
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onAdd({ title, details: details.trim() });
    setTitle("");
    setDetails("");
  };
  return (
    <form onSubmit={submit} className="flex min-w-0 flex-1 flex-col gap-2">
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <TextBox
        id={id}
        oneLine
        value={title}
        onChange={setTitle}
        placeholder={placeholder}
        enterKeyHint="done"
        autoComplete="off"
        className="border-dash text-text focus:border-accent block min-h-11 w-full border border-dashed bg-transparent px-3 py-2.5 text-[16px] outline-none focus:border-solid"
      />
      {title || details ? (
        <>
          <label htmlFor={`${id}-details`} className="sr-only">
            Details
          </label>
          <TextBox
            id={`${id}-details`}
            value={details}
            onChange={setDetails}
            placeholder="Details (optional)"
            className="border-rule bg-surface text-text focus:border-accent block max-h-[40vh] min-h-11 w-full border-2 px-3 py-2.5 text-[16px] outline-none"
          />
          <Button type="submit" tone="accent" className="self-end" disabled={!title.trim()}>
            Add
          </Button>
        </>
      ) : null}
    </form>
  );
}
