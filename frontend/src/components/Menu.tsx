import type { ReactNode } from "react";
import { Button, Menu, MenuItem, MenuTrigger, Popover } from "react-aria-components";

export type MenuAction = {
  label: string;
  onAction: () => void;
  danger?: boolean;
  disabled?: boolean;
};

/** A square popover menu (React Aria: keyboard, focus and screen readers handled). */
export function ActionMenu({
  trigger,
  label,
  actions,
  className = "",
}: {
  trigger: ReactNode;
  label: string;
  actions: MenuAction[];
  className?: string;
}) {
  return (
    <MenuTrigger>
      <Button aria-label={label} className={`outline-none active:opacity-50 ${className}`}>
        {trigger}
      </Button>
      <Popover
        placement="bottom end"
        className="bg-ground border-rule data-[entering]:animate-fade-in min-w-52 border-2 outline-none"
      >
        <Menu className="outline-none">
          {actions.map((a) => (
            <MenuItem
              key={a.label}
              onAction={a.onAction}
              isDisabled={a.disabled}
              className={`label data-[focused]:bg-surface data-[disabled]:text-muted border-hairline flex h-11 items-center border-b px-4 text-[12px] outline-none last:border-b-0 ${
                a.danger ? "text-danger-text" : "text-text"
              }`}
            >
              {a.label}
            </MenuItem>
          ))}
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}
