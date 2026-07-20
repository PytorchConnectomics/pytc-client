import React from "react";
import { fireEvent, render, screen, cleanup } from "@testing-library/react";

import AgentProposalCard from "./AgentProposalCard";

jest.mock("antd", () => ({
  TextArea: ({ autoSize, children, ...props }) => (
    <textarea {...props}>{children}</textarea>
  ),
  Button: ({ children, ...props }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
  Input: {
    TextArea: ({ autoSize, children, ...props }) => (
      <textarea {...props}>{children}</textarea>
    ),
  },
  Space: ({ children }) => <div>{children}</div>,
  Tag: ({ children, ...props }) => <span {...props}>{children}</span>,
  Typography: {
    Text: ({ children, strong, type, ...props }) => (
      <span {...props}>{children}</span>
    ),
  },
}));

describe("AgentProposalCard", () => {
  it("lets users click fields or tap Edit details before approval", () => {
    const onApprove = jest.fn();
    const proposal = {
      id: 12,
      approval_status: "pending",
      type: "start_training_run",
      config_preset: "/project/configs/base.yaml",
      image_path: "/project/subsets/image",
      label_path: "/project/subsets/seg",
      output_path: "/project/outputs/original",
      autopick_parameters: true,
    };

    render(<AgentProposalCard proposal={proposal} onApprove={onApprove} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit details" }));
    fireEvent.change(screen.getByLabelText("Edit Output"), {
      target: { value: "/project/outputs/edited" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve with edits" }));

    expect(onApprove).toHaveBeenCalledWith(proposal, {
      output_path: "/project/outputs/edited",
    });

    cleanup();
    render(<AgentProposalCard proposal={proposal} onApprove={onApprove} />);
    fireEvent.click(screen.getByText("/project/outputs/original"));
    fireEvent.change(screen.getByLabelText("Edit Output"), {
      target: { value: "/project/outputs/edited-direct" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve with edits" }));

    expect(onApprove).toHaveBeenLastCalledWith(proposal, {
      output_path: "/project/outputs/edited-direct",
    });
  });

  it("exposes client-effect paths as editable approval fields", () => {
    const onApprove = jest.fn();
    const proposal = {
      id: 13,
      approval_status: "pending",
      type: "run_client_effects",
      item_label: "Run inference",
      client_effects: {
        set_inference_output_path: "/project/outputs/inference",
      },
    };

    render(<AgentProposalCard proposal={proposal} onApprove={onApprove} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit details" }));
    fireEvent.change(screen.getByLabelText("Edit Output"), {
      target: { value: "/project/outputs/inference-edited" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve with edits" }));

    expect(onApprove).toHaveBeenCalledWith(proposal, {
      inference_output_path: "/project/outputs/inference-edited",
    });
  });

  it("disables actions after decision is recorded", () => {
    render(
      <AgentProposalCard
        proposal={{
          approval_status: "approved",
          type: "start_training_run",
          config_preset: "/tmp/config.yaml",
          image_path: "/tmp/image.tif",
          label_path: "/tmp/label.tif",
        }}
      />,
    );

    expect(screen.getByRole("button", { name: "Approve" }).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Reject" }).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Edit details" })).toBeNull();
  });

  it("keeps long labels and specialist agent badges visible", () => {
    render(
      <AgentProposalCard
        proposal={{
          type: "specialist_inference_validation_and_retraining_review_pipeline",
          rationale: "Verify specialist pipeline visibility.",
          specialist_agent: {
            agent_label: "Inference Specialist Pipeline Visualization",
            agent_short_label: "Inference Specialist",
            agent_color: "#123abc",
            agent_icon_key: "eye",
            agent_border_style: "dashed",
          },
          foo: "bar",
        }}
      />,
    );

    expect(
      screen.getByText(
        "specialist_inference_validation_and_retraining_review_pipeline",
      ).className,
    ).toContain("workflow-proposal-card__type-tag");
    expect(screen.getByText("Inference Specialist")).toBeTruthy();
    expect(screen.getByText("bar")).toBeTruthy();
  });
});
