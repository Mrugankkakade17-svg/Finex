import { expect, test } from '@playwright/test';

const API_BASE_URL = `http://127.0.0.1:${process.env.FINEX_E2E_API_PORT || '8010'}`;

test.describe('E2E 1: Login, Market Search, Watchlist, and Paper Order against Fixture Provider', () => {
  test.beforeEach(async ({ request }) => {
    const resetResponse = await request.post(`${API_BASE_URL}/api/e2e/reset`);
    expect(resetResponse.ok()).toBeTruthy();
  });

  test('completes full primary journey: login -> search -> watchlist -> paper order', async ({ page }) => {
    // Capture the real local-auth bearer token returned on login so PaperTradingPage can send it.
    let issuedAccessToken = '';
    page.on('response', async (response) => {
      if (response.url().endsWith('/api/v1/local-auth/mock-login') && response.status() === 200) {
        const payload = await response.json().catch(() => null);
        const token = payload?.data?.access_token;
        if (typeof token === 'string' && token.length > 0) {
          issuedAccessToken = token;
        }
      }
    });

    // 1. Login as synthetic persona learner-a and confirm onboarding
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Choose a local persona' })).toBeVisible();

    await page.getByRole('button', { name: 'Sign in as learner-a' }).click();
    await expect(page).toHaveURL(/\/onboarding$/);
    await expect(page.getByRole('heading', { name: 'Your local onboarding' })).toBeVisible();
    expect(issuedAccessToken).toMatch(/^[A-Za-z0-9_-]{43}$/);

    // Mirror the issued local bearer token for PaperTradingPage's sessionStorage token resolver.
    await page.evaluate((token) => {
      window.sessionStorage.setItem('finex_access_token', token);
    }, issuedAccessToken);

    await page.getByLabel(/I accept the educational notice/i).check();
    await page.getByRole('button', { name: 'Save consent choice' }).click();
    await expect(page.getByText('Consent choice saved on the local backend.')).toBeVisible();

    await page.getByLabel('Display label').fill('Nilisha E2E');
    await page.getByLabel(/Beginner/i).check();
    await page.getByRole('button', { name: 'Complete onboarding' }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByTestId('local-persona')).toContainText('Nilisha E2E · learner-a');

    // 2. Market Search against fixture provider
    await page.getByRole('link', { name: 'Market Data' }).click();
    await expect(page).toHaveURL(/\/market$/);
    await expect(page.getByTestId('market-mode-badge')).toContainText('Fixture mode');

    await page.getByLabel('Search securities').fill('MSFT');
    await page.getByRole('button', { name: 'Search' }).click();

    const msftResult = page.getByRole('button', { name: /MSFT.*Microsoft Corporation/i });
    await expect(msftResult).toBeVisible();
    await msftResult.click();

    await expect(page.getByText('421.10 USD')).toBeVisible();
    const marketBadge = page.getByTestId('quote-freshness-badge');
    await expect(marketBadge).toHaveAttribute('data-status', 'CACHED');
    await expect(marketBadge).toHaveText('Cached');
    await expect(page.getByTestId('quote-freshness')).toContainText('yfinance-fixture');

    // Also verify outage symbol renders honestly without a fake 0.00 price
    await page.getByLabel('Search securities').fill('DOWN');
    await page.getByRole('button', { name: 'Search' }).click();
    await page.getByRole('button', { name: /DOWN/i }).click();
    await expect(page.getByTestId('quote-unavailable')).toBeVisible();
    await expect(page.getByTestId('quote-freshness-badge')).toHaveAttribute('data-status', 'UNAVAILABLE');
    await expect(page.getByText('0.00 USD')).not.toBeVisible();

    // Re-select MSFT and add to watchlist
    await page.getByLabel('Search securities').fill('MSFT');
    await page.getByRole('button', { name: 'Search' }).click();
    await page.getByRole('button', { name: /MSFT.*Microsoft Corporation/i }).click();
    await page.getByRole('button', { name: 'Add to Watchlist' }).click();
    await expect(page.getByRole('button', { name: 'On Watchlist' })).toBeVisible();

    // 3. Watchlist verification
    await page.getByRole('link', { name: 'Watchlist' }).click();
    await expect(page).toHaveURL(/\/watchlist$/);
    await expect(page.getByTestId('watchlist-freshness-badge-AAPL')).toHaveAttribute('data-status', 'CACHED');
    await expect(page.getByTestId('watchlist-freshness-badge-MSFT')).toHaveAttribute('data-status', 'CACHED');
    await expect(page.getByText('421.10 USD')).toBeVisible();

    // 4. Paper Order execution and server-backed ledger persistence
    await page.getByRole('link', { name: 'Paper Trading' }).click();
    await expect(page).toHaveURL(/\/paper-trading$/);
    await expect(page.getByTestId('paper-simulated-banner')).toBeVisible();
    await expect(page.getByTestId('paper-simulated-badge')).toContainText('SIMULATED');
    await expect(page.getByTestId('paper-cash-balance')).toContainText('$50,000.00 USD');
    await expect(page.getByTestId('paper-positions-empty')).toBeVisible();
    await expect(page.getByTestId('paper-ledger-empty')).toBeVisible();

    // Submit BUY order for 5 shares of AAPL on NASDAQ against fixture price $227.16
    await page.getByLabel('Security Symbol').fill('AAPL');
    await page.getByLabel('Exchange').selectOption('NASDAQ');
    await page.getByLabel('Quantity').fill('5');
    await page.getByRole('button', { name: 'Submit Paper BUY Order' }).click();

    await expect(page.getByTestId('paper-order-confirmation')).toContainText(
      'Filled: Paper BUY order for 5 shares of AAPL (NASDAQ) at $227.16',
    );
    await expect(page.getByTestId('paper-position-AAPL')).toContainText('AAPL');
    await expect(page.getByTestId('paper-position-AAPL')).toContainText('5');
    // 5 * 227.16 = $1,135.80 notional; 10 bps fee = $1.14; remaining cash = $50,000 - $1,136.94 = $48,863.06
    await expect(page.getByTestId('paper-cash-balance')).toContainText('$48,863.06 USD');
    await expect(page.getByTestId('paper-portfolio-value')).toContainText('$1,135.80');
    await expect(page.getByTestId('paper-ledger-section')).toContainText('FILLED');
    await expect(page.getByTestId('paper-ledger-section')).toContainText('AAPL (NASDAQ)');

    // Navigate away and back + reload account to verify state persists from server
    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.getByRole('link', { name: 'Paper Trading' }).click();
    await expect(page).toHaveURL(/\/paper-trading$/);
    await page.getByRole('button', { name: 'Reload account' }).click();

    await expect(page.getByTestId('paper-cash-balance')).toContainText('$48,863.06 USD');
    await expect(page.getByTestId('paper-position-AAPL')).toBeVisible();
    await expect(page.getByTestId('paper-ledger-section')).toContainText('1 recorded entry');
  });

  test('rejects unauthenticated paper trading access honestly without fabricating a balance', async ({ page }) => {
    let issuedAccessToken = '';
    page.on('response', async (response) => {
      if (response.url().endsWith('/api/v1/local-auth/mock-login') && response.status() === 200) {
        const payload = await response.json().catch(() => null);
        if (typeof payload?.data?.access_token === 'string') {
          issuedAccessToken = payload.data.access_token;
        }
      }
    });

    await page.goto('/login');
    await page.getByRole('button', { name: 'Sign in as learner-a' }).click();
    await expect(page).toHaveURL(/\/onboarding$/);
    expect(issuedAccessToken.length).toBe(43);

    // Intentionally do NOT set finex_access_token in sessionStorage
    await page.getByLabel(/I accept the educational notice/i).check();
    await page.getByRole('button', { name: 'Save consent choice' }).click();
    await expect(page.getByText('Consent choice saved on the local backend.')).toBeVisible();
    await page.getByLabel('Display label').fill('Unauth Check');
    await page.getByLabel(/Beginner/i).check();
    await page.getByRole('button', { name: 'Complete onboarding' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole('link', { name: 'Paper Trading' }).click();
    await expect(page).toHaveURL(/\/paper-trading$/);
    await expect(page.getByTestId('paper-simulated-banner')).toBeVisible();
    await expect(page.getByTestId('paper-load-error')).toBeVisible();
    await expect(page.getByTestId('paper-cash-balance')).not.toBeVisible();
  });
});
