import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { TextBox } from "./ui";

function Form({ oneLine, onSubmit }: { oneLine?: boolean; onSubmit: (value: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(value);
      }}
    >
      <TextBox aria-label="text" oneLine={oneLine} value={value} onChange={setValue} />
    </form>
  );
}

describe("TextBox", () => {
  it("one line: Return submits", async () => {
    const onSubmit = vi.fn();
    render(<Form oneLine onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("text"), "A title{Enter}");
    expect(onSubmit).toHaveBeenCalledWith("A title");
  });

  it("one line: pasted line breaks become spaces", async () => {
    const onSubmit = vi.fn();
    render(<Form oneLine onSubmit={onSubmit} />);
    const box = screen.getByLabelText("text");
    box.focus();
    await userEvent.paste("first\nsecond");
    expect(box).toHaveValue("first second");
  });

  it("multi-line: Return is a new line, ⌘Return submits", async () => {
    const onSubmit = vi.fn();
    render(<Form onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("text"), "first{Enter}second");
    expect(onSubmit).not.toHaveBeenCalled();
    await userEvent.keyboard("{Meta>}{Enter}{/Meta}");
    expect(onSubmit).toHaveBeenCalledWith("first\nsecond");
  });
});
