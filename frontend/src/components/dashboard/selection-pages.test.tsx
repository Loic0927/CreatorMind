import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LegacyCreate } from './LegacyCreate';
import { LegacySettings } from './LegacySettings';
import { WireframeInsights } from './WireframeInsights';
import { getAccountContext, updateAccountContext } from '@/lib/postbridge';

const { accountContext } = vi.hoisted(() => ({ accountContext: {
  account_theme: '',
  about_this_account: 'A creator account',
  target_audience: 'Interested viewers',
  tone_keys: ['warm', 'direct'],
  tone_other: '',
  content_formats: ['image'],
  caption_language: 'auto',
  primary_category: 'education',
  primary_category_other: '',
  audience_age_ranges: ['18_24'],
  preferred_hashtags: ['#creator'],
} }));

vi.mock('@/lib/postbridge', () => ({
  getPublishingCapabilities: vi.fn().mockResolvedValue({ items: [] }),
  publishPost: vi.fn(),
  caption: vi.fn(),
  getConnection: vi.fn().mockResolvedValue({ connected: false, configured: true }),
  getAccountContext: vi.fn().mockResolvedValue(accountContext),
  updateAccountContext: vi.fn().mockImplementation(async (_session, value) => value),
  disconnectInstagram: vi.fn(),
  logout: vi.fn(),
  deleteAccount: vi.fn(),
  getAccountInsights: vi.fn().mockResolvedValue({ highlights: [], next_post_suggestion: null, performance_posts: [], needs_refresh_after_hours: 6, sync_status: 'ok' }),
  refreshTrackedPost: vi.fn(),
}));

const session = { accessToken: 'token', expiresAt: '2099-01-01', user: { id: 'user', email: 'creator@example.com' } };
const axeRules = { 'color-contrast': { enabled: false } };

afterEach(() => cleanup());

describe('selection controls on active pages', () => {
  it.each([
    ['Create', () => <LegacyCreate session={session} />],
    ['Settings', () => <LegacySettings session={session} onLogout={() => {}} />],
    ['Insights', () => <WireframeInsights session={session} onOpen={() => {}} />],
  ])('%s has no automated axe violations', async (_name, Page) => {
    const { container } = render(<Page />);
    await waitFor(() => expect(container.querySelector('.unified-select-trigger')).toBeTruthy());
    const result = await axe.run(container, { rules: axeRules });
    expect(result.violations).toEqual([]);
  });

  it('preserves Settings storage keys and values through a save round trip', async () => {
    vi.mocked(getAccountContext).mockResolvedValueOnce(structuredClone(accountContext));
    const user = userEvent.setup();
    render(<LegacySettings session={session} onLogout={() => {}} />);
    const save = await screen.findByRole('button', { name: 'Save settings' });
    await waitFor(() => expect(save).toBeEnabled());
    await user.click(save);
    expect(updateAccountContext).toHaveBeenCalledWith(session, accountContext);
    expect(Object.keys(vi.mocked(updateAccountContext).mock.calls.at(-1)?.[1] ?? {}).sort()).toEqual(Object.keys(accountContext).sort());
  });

  it('keeps the surrounding page layout containers unchanged', async () => {
    const create = render(<LegacyCreate session={session} />);
    const createLayout = create.container.querySelector('.grid.items-start.gap-6.lg\\:grid-cols-2')?.className;
    create.unmount();
    const settings = render(<LegacySettings session={session} onLogout={() => {}} />);
    const settingsLayout = settings.container.firstElementChild?.className;
    settings.unmount();
    const insights = render(<WireframeInsights session={session} onOpen={() => {}} />);
    const insightsLayout = insights.container.firstElementChild?.className;
    expect({ createLayout, settingsLayout, insightsLayout }).toMatchInlineSnapshot(`
      {
        "createLayout": "grid items-start gap-6 lg:grid-cols-2",
        "insightsLayout": "mx-auto w-full max-w-[880px]",
        "settingsLayout": "mx-auto w-full lg:w-[80%]",
      }
    `);
  });
});
