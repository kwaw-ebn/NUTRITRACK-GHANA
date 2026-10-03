import { test, expect } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

test("Onboard a fictional district and save/deactivate a facility through the UI", async () => {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "Welcome to NutriTrack" });
  await user.click(
    screen.getByRole("button", { name: /Set up your organization/ }),
  );
  await user.type(
    screen.getByLabelText("Organization name"),
    "Fictional UI Test Directorate",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("combobox", { name: "Region" }));
  await user.click(await screen.findByRole("option", { name: "Central" }));
  await user.type(screen.getByLabelText("Health district"), "Fictional Health District");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.type(
    screen.getByLabelText("Sub-district 1"),
    "Fictional Subdistrict",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "Add health facility" }));
  await user.type(
    screen.getByLabelText("Facility name"),
    "Fictional Test CHPS",
  );
  await user.selectOptions(
    screen.getByLabelText("Parent sub-district"),
    "Fictional Subdistrict",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.type(
    screen.getByLabelText("Administrator name"),
    "Fictional Administrator",
  );
  await user.type(
    screen.getByLabelText("Email"),
    "ui-" + Date.now() + "@example.org",
  );
  await user.type(
    screen.getByLabelText("Secure password"),
    "FictionalPassword123!",
  );
  await user.type(
    screen.getByLabelText("Authorized setup token"),
    "ui-test-onboarding-token-1234567890",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(await screen.findByLabelText("Child Growth Monitoring"));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(
    screen.getByRole("button", { name: "Complete organization setup" }),
  );
  await screen.findByRole("heading", { name: "Nutrition situation overview" });
  await screen.findByText("Fictional Test CHPS");
  await user.click(
    within(screen.getByRole("navigation")).getByRole("button", {
      name: "Facilities",
    }),
  );
  await user.click(await screen.findByRole("button", { name: "Add facility" }));
  const dialog = screen.getByRole("dialog");
  await user.type(
    within(dialog).getByLabelText("Facility name"),
    "Second Fictional Facility",
  );
  await user.selectOptions(
    within(dialog).getByLabelText("Health sub-district"),
    within(dialog).getByRole("option", { name: "Fictional Subdistrict" }),
  );
  await user.click(within(dialog).getByRole("button", { name: "Save record" }));
  await screen.findByRole("button", { name: "Second Fictional Facility" });
  const row = screen
    .getByRole("button", { name: "Second Fictional Facility" })
    .closest("tr")!;
  await user.click(within(row).getByRole("button", { name: "Edit" }));
  await user.selectOptions(screen.getByLabelText("Status"), "false");
  await user.click(screen.getByRole("button", { name: "Save record" }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  await waitFor(() => {
    const updated = screen
      .getByRole("button", { name: "Second Fictional Facility" })
      .closest("tr")!;
    expect(within(updated).getByText("Inactive")).toBeInTheDocument();
  });
  expect(localStorage.length).toBe(0);
});
