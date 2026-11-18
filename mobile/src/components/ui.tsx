import { Pressable, StyleSheet, Text } from 'react-native';

export function Button({ label, onPress, secondary, disabled }: { label: string; onPress: () => void | Promise<void>; secondary?: boolean; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={[styles.button, secondary && styles.secondary, disabled && styles.disabled]}><Text style={[styles.text, secondary && styles.secondaryText]}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  button: { minHeight: 48, borderRadius: 14, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0284C7' },
  secondary: { backgroundColor: '#E0F2FE' }, text: { color: 'white', fontWeight: '800' }, secondaryText: { color: '#0369A1' }, disabled: { opacity: 0.55 },
});
