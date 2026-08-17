import { Pressable, StyleSheet, Text, View } from 'react-native';

export const GOALS = ['Increase engagement', 'Build brand awareness', 'Educate my audience', 'Promote a product or service', 'Drive website traffic', 'Other'];

export function GoalDropdown({ value, open, onToggle, onSelect }: { value: string; open: boolean; onToggle: () => void; onSelect: (value: string) => void }) {
  return <View style={styles.wrap}><Text style={styles.label}>Goal</Text><Pressable accessibilityRole="button" accessibilityLabel="Choose content goal" accessibilityState={{ expanded: open }} onPress={onToggle} style={styles.trigger}><Text style={value ? styles.value : styles.placeholder}>{value || 'Choose a goal'}</Text><Text>⌄</Text></Pressable>{open && <View accessibilityRole="menu" style={styles.menu}>{GOALS.map((goal) => <Pressable key={goal} accessibilityRole="menuitem" onPress={() => onSelect(goal)} style={styles.option}><Text style={value === goal && styles.selected}>{goal}</Text></Pressable>)}</View>}</View>;
}

const styles = StyleSheet.create({ wrap: { gap: 7 }, label: { fontWeight: '700', color: '#342846' }, trigger: { minHeight: 50, paddingHorizontal: 14, borderWidth: 1, borderColor: '#ddd5e8', backgroundColor: 'white', borderRadius: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, value: { color: '#201633' }, placeholder: { color: '#80778b' }, menu: { borderWidth: 1, borderColor: '#ddd5e8', backgroundColor: 'white', borderRadius: 14, overflow: 'hidden' }, option: { minHeight: 46, paddingHorizontal: 14, justifyContent: 'center', borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#eee8fa' }, selected: { color: '#7c3aed', fontWeight: '800' } });
