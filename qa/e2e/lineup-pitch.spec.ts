import { expect, test } from "@playwright/test";

test("missing player mode shows the starting XI in its match formation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Pratik" }).click();
  await page.getByRole("button", { name: /Eksik oyuncu/ }).click();
  await page.getByRole("button", { name: "Pratiği başlat" }).click();

  const pitch = page.getByRole("group", { name: "Fransa dizilişi: 4-2-3-1" });
  await expect(pitch).toBeVisible();
  await expect(pitch.locator(".lineup-row")).toHaveCount(5);
  await expect(pitch.locator(".lineup-player")).toHaveCount(11);
  await expect(pitch.locator(".lineup-row").first()).toContainText("Olivier Giroud");
  await expect(pitch.locator(".lineup-row").last()).toContainText("Hugo Lloris");
  await expect(pitch.locator(".lineup-row").nth(1).locator(".lineup-player").nth(1)).toHaveText("Eksik oyuncu");
  await expect(pitch).not.toContainText("Griezmann");

  await page.getByRole("textbox", { name: "Oyuncu adı" }).fill("Antoine Griezmann");
  await page.getByRole("button", { name: "Gönder" }).click();
  await expect(page.getByText("Pratik tamamlandı")).toBeVisible();

  await page.getByRole("button", { name: "EN", exact: true }).click();
  await page.getByRole("button", { name: "Play again" }).click();
  await page.getByRole("button", { name: "Start practice" }).click();
  const englishPitch = page.getByRole("group", { name: "France formation: 4-2-3-1" });
  await expect(englishPitch).toContainText("Missing player");
  await expect(englishPitch.locator(".lineup-player")).toHaveCount(11);
});
