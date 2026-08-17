import { Pressable, StyleSheet, Text } from 'react-native';

export function Button({ label, onPress, secondary, disabled }: { label: string; onPress: () => void | Promise<void>; secondary?: boolean; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={[styles.button, secondary && styles.secondary, disabled && styles.disabled]}><Text style={[styles.text, secondary && styles.secondaryText]}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  button: { minHeight: 48, borderRadius: 14, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: '#7c3aed' },
  secondary: { backgroundColor: '#eee8fa' }, text: { color: 'white', fontWeight: '800' }, secondaryText: { color: '#5b21b6' }, disabled: { opacity: 0.55 },
});
