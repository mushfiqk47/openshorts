import * as React from "react";
import { cn } from "../../lib/utils";

// shadcn input on Night Foundry tokens: inset paper fill, hairline border,
// brass focus ring (matches .input-field contract).
const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-input border border-rule2 bg-paper px-3 py-2 text-sm text-ink2 placeholder:text-muted placeholder:opacity-70 focus-visible:outline-none focus-visible:border-brass disabled:cursor-not-allowed disabled:opacity-45",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
