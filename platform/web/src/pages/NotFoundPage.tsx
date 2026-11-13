import { Link } from "react-router-dom";
import { EmptyState } from "@/components/States";
import { Button } from "@/components/ui";

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-3xl p-8">
      <EmptyState title="This page doesn't exist" action={<Link to="/"><Button variant="primary">Back to overview</Button></Link>}>
        Check the address, or use the navigation on the left.
      </EmptyState>
    </div>
  );
}
