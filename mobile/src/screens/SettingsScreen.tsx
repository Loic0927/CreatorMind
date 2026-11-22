import { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as WebBrowser from "expo-web-browser";
import { AiConsentModal } from "../components/AiConsentModal";
import { InstagramAccountCard } from "../components/InstagramAccountCard";
import { Button } from "../components/ui";
import {
  connectInstagram,
  deleteAccount,
  disconnectInstagram,
  getAIProcessingConsent,
  getConnection,
  grantAIProcessingConsent,
  revokeAIProcessingConsent,
} from "../services/api";
import { clearSession } from "../services/auth";
import { legalUrl } from "../config/environment";
import { AIProcessingConsent, InstagramConnection } from "../types";
import { colors } from "../theme/colors";

export function SettingsScreen({
  email,
  accessToken,
  onLogout,
  onAccountDeleted,
}: {
  email: string;
  accessToken: string;
  onLogout: () => Promise<void>;
  onAccountDeleted: () => void;
}) {
  const [connection, setConnection] = useState<InstagramConnection>({
    connected: false,
    configured: false,
    status: "not_connected",
  });
  const [aiConsent, setAiConsent] = useState<AIProcessingConsent | null>(null);
  const [consentModalVisible, setConsentModalVisible] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(
    () =>
      Promise.all([getConnection(accessToken), getAIProcessingConsent(accessToken)])
        .then(([nextConnection, nextConsent]) => {
          setConnection(nextConnection);
          setAiConsent(nextConsent);
          setError("");
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Could not load connection.")),
    [accessToken],
  );
  useEffect(() => {
    load();
  }, [load]);
  const connect = async () => {
    try {
      await connectInstagram(accessToken);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect Instagram.");
    }
  };
  const confirmDisconnect = () =>
    Alert.alert(
      "Disconnect Instagram?",
      "Instagram Insights will stop updating. Your PostBridge account and historical snapshots will be kept.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Disconnect",
          style: "destructive",
          onPress: async () => {
            await disconnectInstagram(accessToken);
            await load();
          },
        },
      ],
    );
  const confirmDelete = () =>
    Alert.alert(
      "Delete PostBridge account?",
      "This permanently deletes your account, connected Instagram data, tracking history and analyses.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete account",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteAccount(accessToken);
              await clearSession();
              onAccountDeleted();
            } catch (e) {
              setError(e instanceof Error ? e.message : "Account deletion failed.");
            }
          },
        },
      ],
    );
  const acceptConsent = async () => {
    setSavingConsent(true);
    setError("");
    try {
      setAiConsent(await grantAIProcessingConsent(accessToken));
      setConsentModalVisible(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save AI processing consent.");
    } finally {
      setSavingConsent(false);
    }
  };
  const revokeConsent = () =>
    Alert.alert("Revoke AI processing consent?", "Existing AI text will be cleared.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Revoke",
        style: "destructive",
        onPress: async () => {
          setSavingConsent(true);
          setError("");
          try {
            setAiConsent(await revokeAIProcessingConsent(accessToken));
          } catch (e) {
            setError(e instanceof Error ? e.message : "Could not revoke AI processing consent.");
          } finally {
            setSavingConsent(false);
          }
        },
      },
    ]);
  const openLegal = (path: "/privacy" | "/terms") => {
    void WebBrowser.openBrowserAsync(legalUrl(path)).catch(() => setError("Could not open this page."));
  };
  return (
    <>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Settings</Text>
        <Text style={styles.sectionTitle}>Account</Text>
        <View style={styles.card}>
          <Text style={styles.email}>{email}</Text>
          <Button label="Log out" onPress={onLogout} secondary />
          <Button label="Delete account" onPress={confirmDelete} secondary />
          <View style={styles.legalLinks}>
            <Pressable accessibilityRole="link" onPress={() => openLegal("/privacy")}>
              <Text style={styles.link}>Privacy</Text>
            </Pressable>
            <Text style={styles.legalSeparator}>·</Text>
            <Pressable accessibilityRole="link" onPress={() => openLegal("/terms")}>
              <Text style={styles.link}>Terms</Text>
            </Pressable>
          </View>
        </View>
        <Text style={styles.sectionTitle}>AI processing</Text>
        <View style={styles.card}>
          <Text style={styles.note}>
            Allow optional Google Gemini features for captions, summaries, comment summaries, and suggestions.
          </Text>
          <Pressable
            accessibilityRole="switch"
            accessibilityState={{
              checked: Boolean(aiConsent?.ai_processing_consented),
              disabled: !aiConsent || savingConsent,
            }}
            disabled={!aiConsent || savingConsent}
            onPress={() => {
              if (aiConsent?.ai_processing_consented) revokeConsent();
              else setConsentModalVisible(true);
            }}
            style={[
              styles.toggle,
              aiConsent?.ai_processing_consented && styles.toggleOn,
              (!aiConsent || savingConsent) && styles.disabled,
            ]}
          >
            <Text style={[styles.toggleText, aiConsent?.ai_processing_consented && styles.toggleTextOn]}>
              {aiConsent?.ai_processing_consented
                ? "AI processing on"
                : aiConsent
                  ? "AI processing off"
                  : "Loading AI setting…"}
            </Text>
          </Pressable>
          <Text style={styles.note}>
            Revoking consent clears your saved AI text. You can still use PostBridge without optional AI features.
          </Text>
        </View>
        <Text style={styles.sectionTitle}>Connected accounts</Text>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <InstagramAccountCard
          connection={connection}
          onConnect={connect}
          onRefresh={load}
          onDisconnect={confirmDisconnect}
        />
      </ScrollView>
      <AiConsentModal
        visible={consentModalVisible}
        busy={savingConsent}
        onAccept={acceptConsent}
        onNotNow={() => setConsentModalVisible(false)}
      />
    </>
  );
}
const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 32, gap: 14 },
  title: { fontSize: 30, lineHeight: 36, fontWeight: "800", color: colors.ink },
  sectionTitle: { fontWeight: "800", fontSize: 18, color: colors.ink },
  card: {
    padding: 18,
    borderRadius: 18,
    backgroundColor: colors.surface,
    gap: 14,
    borderWidth: 1,
    borderColor: colors.line,
  },
  email: { fontWeight: "700", color: colors.ink },
  error: { color: colors.danger },
  note: { color: colors.inkSoft, fontSize: 13, lineHeight: 19 },
  legalLinks: { flexDirection: "row", justifyContent: "center", gap: 9 },
  link: { color: colors.primary, fontSize: 13, fontWeight: "800", textDecorationLine: "underline" },
  legalSeparator: { color: colors.muted, fontSize: 13 },
  toggle: {
    minHeight: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
    backgroundColor: colors.selected,
  },
  toggleOn: { backgroundColor: colors.primary },
  toggleText: { color: colors.selectedInk, fontWeight: "800" },
  toggleTextOn: { color: colors.white },
  disabled: { opacity: 0.55 },
});
