import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { UnifiedSelect } from './UnifiedSelect';

const options = [
  { value: 'one', label: 'One' },
  { value: 'two', label: 'Two' },
  { value: 'other', label: 'Other' },
];

describe('UnifiedSelect', () => {
  it('supports single selection, keyboard navigation, and focus return', async () => {
    const user = userEvent.setup();
    const change = vi.fn();
    render(<UnifiedSelect label="Goal" options={options} value="one" onChange={change} />);
    const trigger = screen.getByRole('button', { name: /choose goal/i });
    await user.click(trigger);
    const listbox = screen.getByRole('listbox', { name: 'Goal' });
    listbox.focus();
    await user.keyboard('{End}{Enter}');
    expect(change).toHaveBeenCalledWith('other');
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('supports multi-select max and chip overflow', async () => {
    const user = userEvent.setup();
    const change = vi.fn();
    render(<UnifiedSelect label="Tone" options={[...options, { value: 'four', label: 'Four' }]} values={['one', 'two', 'other']} onValuesChange={change} multiple max={3} />);
    expect(screen.getByText('+1')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /choose tone/i }));
    expect(screen.getByText('3 of 3 selected')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Four' })).toHaveAttribute('aria-disabled', 'true');
  });

  it('renders compact, Other, disabled, and error variants', () => {
    const update = vi.fn();
    const { rerender } = render(<UnifiedSelect label="Sort" options={options} value="one" onChange={vi.fn()} compact />);
    expect(screen.getByText('Sort: One')).toBeInTheDocument();
    rerender(<UnifiedSelect label="Category" options={options} value="other" onChange={vi.fn()} otherOptionValue="other" otherValue="Custom" onOtherValueChange={update} error="Invalid category" />);
    fireEvent.change(screen.getByLabelText('Category other value'), { target: { value: 'Creator' } });
    expect(update).toHaveBeenCalledWith('Creator');
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid category');
    rerender(<UnifiedSelect label="Disabled" options={options} disabled />);
    expect(screen.getByRole('button', { name: /choose disabled/i })).toBeDisabled();
  });

  it('adds search for more than eight options', async () => {
    const user = userEvent.setup();
    const many = Array.from({ length: 9 }, (_, index) => ({ value: String(index), label: `Option ${index}` }));
    render(<UnifiedSelect label="Language" options={many} value="0" onChange={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /choose language/i }));
    await user.type(screen.getByRole('textbox', { name: /search language/i }), '8');
    expect(screen.getByRole('option', { name: 'Option 8' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Option 1' })).not.toBeInTheDocument();
  });

  it('keeps only one panel open', async () => {
    const user = userEvent.setup();
    render(<><UnifiedSelect label="First" options={options} /><UnifiedSelect label="Second" options={options} /></>);
    await user.click(screen.getByRole('button', { name: /choose first/i }));
    await user.click(screen.getByRole('button', { name: /choose second/i }));
    expect(screen.getByRole('button', { name: /choose first/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('button', { name: /choose second/i })).toHaveAttribute('aria-expanded', 'true');
  });

  it('allows React Aria to flip a panel near the viewport bottom', async () => {
    const user = userEvent.setup();
    const makeRect = (x: number, y: number, width: number, height: number) => ({ x, y, width, height, top: y, left: x, right: x + width, bottom: y + height, toJSON: () => ({}) }) as DOMRect;
    const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.classList.contains('unified-select-trigger')) return makeRect(20, 710, 240, 48);
      if (this.classList.contains('unified-select-popover')) return makeRect(20, 0, 240, 280);
      return makeRect(0, 0, 0, 0);
    });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 768 });
    render(<UnifiedSelect label="Near bottom" options={options} value="one" onChange={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /choose near bottom/i }));
    await waitFor(() => expect(document.querySelector('.unified-select-popover')).toHaveAttribute('data-placement', 'top'));
    rect.mockRestore();
  });

  it('renders the 390px bottom sheet and remains axe-clean', async () => {
    const original = window.matchMedia;
    window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    const user = userEvent.setup();
    const { container } = render(<UnifiedSelect label="Mobile goal" options={options} value="one" onChange={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /choose mobile goal/i }));
    expect(screen.getByRole('dialog', { name: 'Mobile goal' })).toBeInTheDocument();
    const result = await axe.run(container.ownerDocument, { rules: { 'color-contrast': { enabled: false }, 'document-title': { enabled: false }, 'html-has-lang': { enabled: false } } });
    expect(result.violations).toEqual([]);
    act(() => { window.matchMedia = original; });
  });

  it('keeps placeholder and selected token contrast at WCAG AA', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8');
    const token = (name: string) => css.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, 'i'))?.[1] ?? '';
    expect(contrast(token('select-muted'), '#ffffff')).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token('select-selected-ink'), token('select-selected-bg'))).toBeGreaterThanOrEqual(4.5);
  });
});

function contrast(foreground: string, background: string) {
  const luminance = (hex: string) => {
    const channels = hex.slice(1).match(/../g)?.map((value) => parseInt(value, 16) / 255) ?? [];
    const [r = 0, g = 0, b = 0] = channels.map((value) => value <= .03928 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return .2126 * r + .7152 * g + .0722 * b;
  };
  const [lighter, darker] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (lighter + .05) / (darker + .05);
}
