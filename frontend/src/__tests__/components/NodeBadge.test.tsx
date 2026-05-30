import { render, screen } from "@testing-library/react";
import { NodeBadge } from "@/components/ui/NodeBadge";

describe("NodeBadge", () => {
  it("renders the kind label", () => {
    render(<NodeBadge kind="skill" managed={true} />);
    expect(screen.getByText("skill")).toBeInTheDocument();
  });

  it("shows managed badge when managed=true", () => {
    render(<NodeBadge kind="rule" managed={true} />);
    expect(screen.getByText("managed")).toBeInTheDocument();
  });

  it("shows bundled badge when managed=false", () => {
    render(<NodeBadge kind="rule" managed={false} />);
    expect(screen.getByText("bundled")).toBeInTheDocument();
  });
});
