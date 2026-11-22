import { colors } from "../theme/colors";

export const selectTokens = {
  ink: colors.ink,
  muted: colors.muted,
  border: colors.line,
  primary: colors.primary,
  selectedBackground: colors.selected,
  selectedInk: colors.selectedInk,
  hover: colors.subtle,
  error: colors.danger,
  checkboxBorder: colors.checkboxBorder,
  radius: 12,
  optionRadius: 8,
  triggerHeight: 48,
  compactHeight: 36,
  optionHeight: 48,
} as const;
