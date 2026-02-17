import {
  CircleCheck,
  CircleX,
  CircleAlert,
} from "lucide-react"

export function PermissionStatus({ permission }: { permission: "explicitly_permitted" | "explicitly_prohibited" | "conditional_ambiguous" }) {
  switch (permission) {
    case "explicitly_permitted":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm">
          <CircleCheck className="size-4 text-emerald-600" />
          Permitted
        </span>
      )
    case "explicitly_prohibited":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm">
          <CircleX className="size-4 text-red-500" />
          Prohibited
        </span>
      )
    case "conditional_ambiguous":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm">
          <CircleAlert className="size-4 text-amber-500" />
          Conditional
        </span>
      )
  }
}
