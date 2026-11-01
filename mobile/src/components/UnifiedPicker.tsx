import { useCallback, useMemo, useRef, useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { selectTokens as token } from './selectTokens';

export type PickerOption = { value: string; label: string; disabled?: boolean };

type UnifiedPickerProps = {
  label: string;
  helper?: string;
  options: readonly PickerOption[];
  value?: string;
  values?: readonly string[];
  onChange?: (value: string) => void;
  onValuesChange?: (values: string[]) => void;
  multiple?: boolean;
  max?: number;
  compact?: boolean;
  placeholder?: string;
  disabled?: boolean;
  error?: string;
  title?: string;
  otherOptionValue?: string;
  otherValue?: string;
  onOtherValueChange?: (value: string) => void;
  otherPlaceholder?: string;
};

let openPicker: { id: symbol; close: () => void } | null = null;

export function UnifiedPicker({
  label, helper, options, value = '', values = [], onChange, onValuesChange, multiple = false,
  max, compact = false, placeholder = 'Choose an option', disabled = false, error, title,
  otherOptionValue, otherValue = '', onOtherValueChange, otherPlaceholder = 'Please specify',
}: UnifiedPickerProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const pickerId = useRef(Symbol('picker')).current;
  const selected = useMemo(() => new Set(multiple ? values : value ? [value] : []), [multiple, value, values]);
  const selectedOptions = options.filter((option) => selected.has(option.value));
  const atMax = multiple && max != null && values.length >= max;
  const searchable = options.length > 8;
  const visible = searchable && search ? options.filter((option) => option.label.toLocaleLowerCase().includes(search.toLocaleLowerCase())) : options;
  const showOther = Boolean(otherOptionValue && selected.has(otherOptionValue) && onOtherValueChange);

  const close = useCallback(() => {
    setOpen(false);
    if (openPicker?.id === pickerId) openPicker = null;
  }, [pickerId]);
  const show = () => {
    openPicker?.close();
    openPicker = { id: pickerId, close };
    setSearch('');
    setOpen(true);
  };
  const choose = (nextValue: string) => {
    if (!multiple) {
      onChange?.(nextValue);
      close();
      return;
    }
    const next = values.includes(nextValue) ? values.filter((item) => item !== nextValue) : [...values, nextValue];
    if (max != null && next.length > max) return;
    onValuesChange?.(options.filter((option) => next.includes(option.value)).map((option) => option.value));
  };

  const firstLabel = selectedOptions[0]?.label;
  const valueLabel = compact && firstLabel ? `${label}: ${firstLabel}` : firstLabel || placeholder;
  return <View style={[styles.field, compact && styles.compactField]}>
    {!compact ? <View style={styles.labelRow}><Text style={styles.label}>{label}</Text>{helper ? <Text style={styles.helper}>{helper}</Text> : null}</View> : null}
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={compact ? label : `Choose ${label}`}
      accessibilityHint={selectedOptions.length ? `${selectedOptions.map((item) => item.label).join(', ')} selected` : undefined}
      accessibilityState={{ expanded: open, disabled }}
      hitSlop={compact ? { top: 4, bottom: 4, left: 0, right: 0 } : undefined}
      disabled={disabled}
      onPress={show}
      style={({ pressed }) => [styles.trigger, compact && styles.compactTrigger, error && styles.triggerError, disabled && styles.disabled, pressed && styles.pressed]}
    >
      {multiple && selectedOptions.length ? <View style={styles.chips}>
        {selectedOptions.slice(0, 2).map((option) => <View key={option.value} style={styles.chip}><Text numberOfLines={1} style={styles.chipText}>{option.label}</Text></View>)}
        {selectedOptions.length > 2 ? <View style={styles.chip}><Text style={styles.chipText}>+{selectedOptions.length - 2}</Text></View> : null}
      </View> : <Text numberOfLines={1} style={[styles.value, !selectedOptions.length && styles.placeholder, compact && styles.compactValue]}>{valueLabel}</Text>}
      <Chevron open={open} />
    </Pressable>
    {showOther ? <TextInput accessibilityLabel={`${label} other value`} value={otherValue} onChangeText={onOtherValueChange} placeholder={otherPlaceholder} placeholderTextColor={token.muted} style={styles.other} /> : null}
    {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
    <Modal visible={open} transparent animationType="slide" onRequestClose={close} statusBarTranslucent>
      <View style={styles.scrim} accessibilityViewIsModal>
        <Pressable accessibilityRole="button" accessibilityLabel={`Close ${title || label}`} onPress={close} style={StyleSheet.absoluteFill} />
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <Text style={styles.title}>{title || label}</Text>
          {searchable ? <TextInput accessibilityLabel={`Search ${label}`} value={search} onChangeText={setSearch} placeholder="Search options" placeholderTextColor={token.muted} style={styles.search} autoCorrect={false} /> : null}
          <FlatList
            data={visible}
            keyExtractor={(item) => item.value}
            style={styles.list}
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) => {
              const isSelected = selected.has(item.value);
              const isDisabled = Boolean(item.disabled || (atMax && !isSelected));
              return <Pressable
                accessibilityRole={multiple ? 'checkbox' : 'radio'}
                accessibilityState={{ checked: isSelected, disabled: isDisabled }}
                disabled={isDisabled}
                onPress={() => choose(item.value)}
                style={({ pressed }) => [styles.option, isSelected && styles.optionSelected, isDisabled && styles.disabledOption, pressed && styles.optionPressed]}
              >
                {multiple ? <View style={[styles.checkbox, isSelected && styles.checkboxSelected]}>{isSelected ? <Check color="white" /> : null}</View> : null}
                <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>{item.label}</Text>
                {!multiple && isSelected ? <View style={styles.singleCheck}><Check color={token.primary} /></View> : null}
              </Pressable>;
            }}
          />
          {multiple && max != null ? <Text accessibilityLiveRegion="polite" style={styles.footer}>{values.length} of {max} selected</Text> : null}
          {multiple ? <Pressable accessibilityRole="button" onPress={close} style={styles.done}><Text style={styles.doneText}>Done</Text></Pressable> : null}
        </View>
      </View>
    </Modal>
  </View>;
}

function Chevron({ open }: { open: boolean }) {
  return <View accessibilityElementsHidden style={[styles.chevron, open && styles.chevronOpen]}><View style={styles.chevronLeft} /><View style={styles.chevronRight} /></View>;
}

function Check({ color }: { color: string }) {
  return <View accessibilityElementsHidden style={styles.checkWrap}><View style={[styles.checkShort, { borderColor: color }]} /><View style={[styles.checkLong, { borderColor: color }]} /></View>;
}

const styles = StyleSheet.create({
  field: { width: '100%' }, compactField: { width: 150 }, labelRow: { flexDirection: 'row', alignItems: 'baseline', gap: 5, marginBottom: 8 },
  label: { color: token.ink, fontSize: 14, fontWeight: '700' }, helper: { color: token.muted, fontSize: 14 },
  trigger: { minHeight: token.triggerHeight, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, borderWidth: 1, borderColor: token.border, borderRadius: token.radius, backgroundColor: 'white', paddingHorizontal: 14, paddingVertical: 6 },
  compactTrigger: { minHeight: token.compactHeight, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 4 }, triggerError: { borderColor: token.error, borderWidth: 2 }, disabled: { opacity: .5 }, pressed: { backgroundColor: token.hover },
  value: { flex: 1, color: token.ink, fontSize: 15 }, compactValue: { color: token.selectedInk, fontSize: 13, fontWeight: '700' }, placeholder: { color: token.muted },
  chips: { minWidth: 0, flex: 1, flexDirection: 'row', gap: 5 }, chip: { maxWidth: '45%', borderRadius: 999, backgroundColor: token.selectedBackground, paddingHorizontal: 8, paddingVertical: 3 }, chipText: { color: token.selectedInk, fontSize: 12 },
  chevron: { width: 16, height: 16, position: 'relative' }, chevronOpen: { transform: [{ rotate: '180deg' }] }, chevronLeft: { position: 'absolute', left: 2, top: 6, width: 8, borderBottomWidth: 2, borderColor: token.muted, transform: [{ rotate: '45deg' }] }, chevronRight: { position: 'absolute', right: 0, top: 6, width: 8, borderBottomWidth: 2, borderColor: token.muted, transform: [{ rotate: '-45deg' }] },
  other: { minHeight: token.triggerHeight, marginTop: 8, borderWidth: 1, borderColor: token.border, borderRadius: token.radius, backgroundColor: 'white', paddingHorizontal: 14, color: token.ink, fontSize: 15 }, error: { marginTop: 6, color: token.error, fontSize: 13 },
  scrim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(30,22,51,.42)' }, sheet: { maxHeight: '80%', borderTopLeftRadius: 16, borderTopRightRadius: 16, backgroundColor: 'white', padding: 6, paddingBottom: 14, shadowColor: token.ink, shadowOpacity: .12, shadowRadius: 24, shadowOffset: { width: 0, height: -8 }, elevation: 16 },
  handle: { width: 40, height: 4, alignSelf: 'center', marginTop: 2, marginBottom: 10, borderRadius: 999, backgroundColor: token.checkboxBorder }, title: { marginHorizontal: 8, marginBottom: 8, color: token.ink, fontSize: 18, fontWeight: '800' },
  search: { minHeight: token.triggerHeight, marginBottom: 6, borderWidth: 1, borderColor: token.border, borderRadius: token.radius, paddingHorizontal: 14, color: token.ink, fontSize: 15 }, list: { maxHeight: 360 },
  option: { minHeight: token.optionHeight, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: token.optionRadius, paddingHorizontal: 10, paddingVertical: 8 }, optionSelected: { backgroundColor: token.selectedBackground }, optionPressed: { backgroundColor: token.hover }, disabledOption: { opacity: .42 }, optionText: { flex: 1, color: token.ink, fontSize: 15 }, optionTextSelected: { color: token.selectedInk },
  checkbox: { width: 18, height: 18, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: token.checkboxBorder, borderRadius: 5 }, checkboxSelected: { borderColor: token.primary, backgroundColor: token.primary }, singleCheck: { width: 18, height: 18, alignItems: 'center', justifyContent: 'center' },
  checkWrap: { width: 14, height: 14 }, checkShort: { position: 'absolute', left: 1, top: 7, width: 6, borderBottomWidth: 2, transform: [{ rotate: '45deg' }] }, checkLong: { position: 'absolute', left: 5, top: 5, width: 9, borderBottomWidth: 2, transform: [{ rotate: '-45deg' }] },
  footer: { paddingHorizontal: 10, paddingTop: 7, color: token.muted, fontSize: 12, textAlign: 'right' }, done: { minHeight: 48, marginHorizontal: 4, marginTop: 8, alignItems: 'center', justifyContent: 'center', borderRadius: token.radius, backgroundColor: token.primary }, doneText: { color: 'white', fontSize: 15, fontWeight: '800' },
});
