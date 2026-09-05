/* eslint-disable react-refresh/only-export-components -- buttonVariants is
   intentionally shared so callers can reuse button styles on non-button
   elements (canonical shadcn pattern). */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "../../lib/utils";

// shadcn button — variants mapped onto Night Foundry tokens (design.md):
// one accent (brass), hairline borders, pill radius, lowercase labels.
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium lowercase transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass focus-visible:ring-offset-2 focus-visible:ring-offset-paper disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-brass text-brassink hover:brightness-110 active:translate-y-px",
        secondary: "bg-paper3 text-ink2 hover:brightness-125 active:translate-y-px",
        outline:
          "border border-rule2 bg-transparent text-ink hover:border-brass active:translate-y-px",
        ghost: "text-ink2 hover:bg-paper3 hover:text-ink",
        destructive:
          "border border-danger/40 text-danger hover:bg-danger/10",
        link: "text-ink2 underline-offset-4 hover:underline hover:text-brass",
      },
      size: {
        default: "h-10 px-6 py-2",
        sm: "h-8 px-4 text-xs",
        lg: "h-12 px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
