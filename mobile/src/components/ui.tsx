import { Pressable, StyleSheet, Text } from "react-native";
import { colors } from "../theme/colors";

export function Button({
  label,
  onPress,
  secondary,
  disabled,
}: {
  label: string;
  onPress: () => void | Promise<void>;
  secondary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={[styles.button, secondary && styles.secondary, disabled && styles.disabled]}
    >
      <Text style={[styles.text, secondary && styles.secondaryText]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 48,
    borderRadius: 14,
    paddingHorizontal: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
  },
  secondary: { backgroundColor: colors.selected },
  text: { color: colors.white, fontWeight: "800" },
  secondaryText: { color: colors.selectedInk },
  disabled: { opacity: 0.55 },
});
