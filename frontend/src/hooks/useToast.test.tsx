import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ToastProvider } from "./useToast";

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

function fire(message: string, status = 502) {
  window.dispatchEvent(new CustomEvent("api-error", { detail: { status, message } }));
}

describe("ToastProvider api-error listener", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => {
      root.render(<ToastProvider><div>app</div></ToastProvider>);
    });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  it("shows a toast for an api-error event", async () => {
    await act(async () => fire("mcp-server không phản hồi"));
    const toasts = container.querySelectorAll("[data-toast]");
    expect(toasts.length).toBe(1);
    expect(toasts[0].textContent).toBe("mcp-server không phản hồi");
  });

  it("de-duplicates identical messages that are still visible", async () => {
    await act(async () => {
      fire("mcp-server không phản hồi");
      fire("mcp-server không phản hồi");
      fire("mcp-server không phản hồi");
    });
    expect(container.querySelectorAll("[data-toast]").length).toBe(1);
  });

  it("keeps different messages", async () => {
    await act(async () => {
      fire("lỗi A");
      fire("lỗi B");
    });
    expect(container.querySelectorAll("[data-toast]").length).toBe(2);
  });
});
