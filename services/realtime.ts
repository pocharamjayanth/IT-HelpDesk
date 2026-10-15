import { supabase } from "../lib/supabase";

export function subscribeToTickets(onTicketChange: (payload: any) => void) {
  const channel = supabase
    .channel("realtime-tickets")
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "tickets" },
      (payload) => {
        console.log("⚡ Live ticket update received:", payload);
        onTicketChange(payload);
      }
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
}
