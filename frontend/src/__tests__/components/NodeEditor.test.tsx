import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NodeEditor } from "@/components/nodes/NodeEditor";

const mockNode = {
  id: "skills/test-skill",
  title: "Test Skill",
  description: "A test skill",
  kind: "skill" as const,
  path: "server/managed/skills/test-skill/SKILL.md",
  managed: true,
  body: "# Test Skill\n\nSome content.",
  frontmatter: { name: "test-skill", description: "A test skill" },
  links: [],
  inbound_links: [],
};

describe("NodeEditor", () => {
  it("renders node title in the name field", () => {
    render(<NodeEditor node={mockNode} onSave={jest.fn()} onDelete={jest.fn()} />);
    expect(screen.getByDisplayValue("test-skill")).toBeInTheDocument();
  });

  it("renders the body in the textarea", () => {
    render(<NodeEditor node={mockNode} onSave={jest.fn()} onDelete={jest.fn()} />);
    expect(screen.getByDisplayValue(/# Test Skill/)).toBeInTheDocument();
  });

  it("calls onSave with updated body when Save is clicked", async () => {
    const onSave = jest.fn();
    const user = userEvent.setup();
    render(<NodeEditor node={mockNode} onSave={onSave} onDelete={jest.fn()} />);
    const textarea = screen.getByRole("textbox", { name: /body/i });
    await user.clear(textarea);
    await user.type(textarea, "# Updated");
    await user.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ body: "# Updated" }),
    );
  });

  it("calls onDelete when Delete is clicked and confirmed", async () => {
    const onDelete = jest.fn();
    const user = userEvent.setup();
    render(<NodeEditor node={mockNode} onSave={jest.fn()} onDelete={onDelete} />);
    await user.click(screen.getByRole("button", { name: /delete/i }));
    // confirm dialog
    await user.click(screen.getByRole("button", { name: /confirm/i }));
    expect(onDelete).toHaveBeenCalled();
  });
});
