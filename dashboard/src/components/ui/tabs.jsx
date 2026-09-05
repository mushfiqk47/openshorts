import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "../../lib/utils";

// shadcn tabs restyled as the app's underline tab row (MediaInput pattern):
// active tab gets brass text + brass underline, inactive stays muted.
const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("flex gap-4 sm:gap-6 border-b border-rule", className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-1 pb-3 -mb-px text-sm lowercase text-muted transition-colors hover:text-ink2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass data-[state=active]:border-brass data-[state=active]:text-ink [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:hidden [&_svg]:sm:block",
      className
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn("focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass", className)}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
