import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { colors } from "../theme/colors";

export function AiConsentModal({
  visible,
  busy = false,
  onAccept,
  onNotNow,
}: {
  visible: boolean;
  busy?: boolean;
  onAccept: () => void | Promise<void>;
  onNotNow: () => void;
}) {
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={busy ? undefined : onNotNow}
    >
      <View style={styles.backdrop}>
        <View accessibilityViewIsModal style={styles.sheet}>
          <Text style={styles.eyebrow}>OPTIONAL AI FEATURES</Text>
          <Text accessibilityRole="header" style={styles.title}>
            Review AI data use
          </Text>
          <Text style={styles.body}>
            If you choose to use an AI feature, PostBridge sends the relevant data to the Google Gemini API to create a
            caption, summary, comment summary, or next-post suggestion.
          </Text>
          <Text style={styles.listTitle}>This can include:</Text>
          <Text style={styles.body}>
            • post media and captions;{"\n"}• audience comment text; and{"\n"}• performance facts about your posts.
          </Text>
          <Text style={styles.body}>
            AI processing runs only after you accept this notice and request an AI-powered feature.
          </Text>
          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={onNotNow}
              style={[styles.button, styles.notNow, busy && styles.disabled]}
            >
              <Text style={styles.notNowText}>Not now</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={() => void onAccept()}
              style={[styles.button, styles.accept, busy && styles.disabled]}
            >
              <Text style={styles.acceptText}>{busy ? "Saving…" : "Accept"}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "center",
    padding: 20,
    backgroundColor: colors.overlay,
  },
  sheet: { gap: 14, borderRadius: 22, backgroundColor: colors.surface, padding: 22 },
  eyebrow: { color: colors.primaryHover, fontSize: 11, fontWeight: "900", letterSpacing: 1 },
  title: { color: colors.ink, fontSize: 24, fontWeight: "900" },
  body: { color: colors.inkSoft, fontSize: 14, lineHeight: 21 },
  listTitle: { color: colors.ink, fontSize: 14, fontWeight: "800" },
  actions: { flexDirection: "row", gap: 10, marginTop: 6 },
  button: { minHeight: 48, flex: 1, alignItems: "center", justifyContent: "center", borderRadius: 14, padding: 12 },
  notNow: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  accept: { backgroundColor: colors.primary },
  notNowText: { color: colors.inkSoft, fontWeight: "800" },
  acceptText: { color: colors.white, fontWeight: "800" },
  disabled: { opacity: 0.55 },
});
