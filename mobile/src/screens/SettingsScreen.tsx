import { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as WebBrowser from "expo-web-browser";
import { InstagramAccountCard } from "../components/InstagramAccountCard";
import { Button } from "../components/ui";
import { connectInstagram, deleteAccount, disconnectInstagram, getConnection } from "../services/api";
import { clearSession } from "../services/auth";
import { legalUrl } from "../config/environment";
import { InstagramConnection } from "../types";
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
  const [error, setError] = useState("");
  const load = useCallback(
    () =>
      getConnection(accessToken)
        .then((nextConnection) => {
          setConnection(nextConnection);
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
  const openLegal = (path: "/privacy" | "/terms") => {
    void WebBrowser.openBrowserAsync(legalUrl(path)).catch(() => setError("Could not open this page."));
  };
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.sectionTitle}>Account</Text>
      <View style={styles.card}>
        <Text style={styles.email}>{email}</Text>
        <Button label="Log out" onPress={onLogout} secondary />
        <Button label="Delete account" onPress={confirmDelete} secondary />
      </View>
      <Text style={styles.sectionTitle}>Connected accounts</Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <InstagramAccountCard
        connection={connection}
        onConnect={connect}
        onRefresh={load}
        onDisconnect={confirmDisconnect}
      />
      <View style={styles.legalLinks}>
        <Pressable accessibilityRole="link" onPress={() => openLegal("/privacy")}>
          <Text style={styles.link}>Privacy</Text>
        </Pressable>
        <Text style={styles.legalSeparator}>·</Text>
        <Pressable accessibilityRole="link" onPress={() => openLegal("/terms")}>
          <Text style={styles.link}>Terms</Text>
        </Pressable>
      </View>
    </ScrollView>
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
  legalLinks: { flexDirection: "row", justifyContent: "center", gap: 9, paddingTop: 8 },
  link: { color: colors.primary, fontSize: 13, fontWeight: "800", textDecorationLine: "underline" },
  legalSeparator: { color: colors.muted, fontSize: 13 },
});
