import { expect, test } from "@playwright/test";

test.describe("live room and accessibility smoke", () => {
  test("two browser clients see the same server-authoritative round", async ({ browser }) => {
    const firstContext = await browser.newContext({ locale: "tr-TR" });
    const secondContext = await browser.newContext({ locale: "tr-TR" });
    const first = await firstContext.newPage();
    const second = await secondContext.newPage();

    await first.goto("/");
    await first.getByRole("link", { name: "Çok oyunculu" }).click();
    await first.getByRole("button", { name: "Oluştur" }).click();
    const roomCode = await first.locator(".room-code").innerText();
    expect(roomCode).toMatch(/^[A-Z0-9]{6}$/);

    await second.goto("/");
    await second.getByRole("link", { name: "Çok oyunculu" }).click();
    await second.getByLabel("6 haneli oda kodu").fill(roomCode);
    await second.getByRole("button", { name: "Katıl" }).click();
    await expect(first.locator(".participant-list .participant-row")).toHaveCount(2);

    await first.getByRole("button", { name: "Maçı başlat" }).click();
    await expect(first.locator(".multiplayer-play")).toBeVisible();
    await expect(second.locator(".multiplayer-play")).toBeVisible();
    await expect(first.locator(".multiplayer-play h2")).toHaveText(await second.locator(".multiplayer-play h2").innerText());

    await firstContext.close();
    await secondContext.close();
  });

  test("interactive controls expose names and selected state to assistive technology", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Pratik" }).click();
    const hangman = page.getByRole("button", { name: "Çöp adam" });
    await expect(hangman).toHaveAttribute("aria-pressed", "false");
    await hangman.click();
    await expect(hangman).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("link", { name: "Ranked" }).click();
    const unlabeledInputs = await page.locator("input").evaluateAll((inputs) => inputs.filter((input) => {
      const hasLabel = Boolean(input.getAttribute("aria-label") || input.getAttribute("aria-labelledby"));
      return !hasLabel;
    }).length);
    expect(unlabeledInputs).toBe(0);
    await page.keyboard.press("Tab");
    expect(await page.locator(":focus-visible").count()).toBeGreaterThan(0);
  });
});
