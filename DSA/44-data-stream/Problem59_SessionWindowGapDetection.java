import java.util.*;

/**
 * Problem 59: Session Window with Gap Detection
 * 
 * Production Relevance:
 * - Models user sessions: group events until inactivity gap exceeds threshold
 * - Used in web analytics (Google Analytics sessions), fraud detection, IoT device monitoring
 * - Unlike fixed windows, session windows are dynamic and per-key
 * - Session merging: two sessions merge if gap between them closes
 * 
 * Architect Considerations:
 * - State per session can grow unbounded for long-active sessions; need max session duration
 * - Session merging on late arrivals requires mutable window state
 * - Memory: number of concurrent open sessions = number of active users
 */
public class Problem59_SessionWindowGapDetection {

    static class SessionEvent {
        String userId;
        String action;
        long timestamp;

        SessionEvent(String userId, String action, long timestamp) {
            this.userId = userId;
            this.action = action;
            this.timestamp = timestamp;
        }
    }

    static class Session {
        String userId;
        long startTime;
        long endTime;
        List<SessionEvent> events = new ArrayList<>();

        Session(SessionEvent first) {
            this.userId = first.userId;
            this.startTime = first.timestamp;
            this.endTime = first.timestamp;
            this.events.add(first);
        }

        void addEvent(SessionEvent event) {
            events.add(event);
            endTime = Math.max(endTime, event.timestamp);
            startTime = Math.min(startTime, event.timestamp);
        }

        void merge(Session other) {
            events.addAll(other.events);
            events.sort(Comparator.comparingLong(e -> e.timestamp));
            startTime = Math.min(startTime, other.startTime);
            endTime = Math.max(endTime, other.endTime);
        }

        long duration() { return endTime - startTime; }

        @Override
        public String toString() {
            return String.format("Session[%s, %d-%d, duration=%dms, events=%d]",
                    userId, startTime, endTime, duration(), events.size());
        }
    }

    static class SessionWindowProcessor {
        private final long gapMs;
        private final long maxSessionDurationMs;
        private final Map<String, List<Session>> activeSessions = new HashMap<>();
        private final List<Session> closedSessions = new ArrayList<>();

        SessionWindowProcessor(long gapMs, long maxSessionDurationMs) {
            this.gapMs = gapMs;
            this.maxSessionDurationMs = maxSessionDurationMs;
        }

        public void processEvent(SessionEvent event) {
            List<Session> userSessions = activeSessions.computeIfAbsent(event.userId, k -> new ArrayList<>());

            // Find session this event belongs to (within gap of any existing session boundary)
            Session target = null;
            List<Session> toMerge = new ArrayList<>();

            for (Session s : userSessions) {
                if (event.timestamp >= s.startTime - gapMs && event.timestamp <= s.endTime + gapMs) {
                    toMerge.add(s);
                }
            }

            if (toMerge.isEmpty()) {
                // New session
                target = new Session(event);
                userSessions.add(target);
            } else {
                // Merge all overlapping sessions
                target = toMerge.get(0);
                target.addEvent(event);
                for (int i = 1; i < toMerge.size(); i++) {
                    target.merge(toMerge.get(i));
                    userSessions.remove(toMerge.get(i));
                }
            }

            // Check max session duration
            if (target.duration() > maxSessionDurationMs) {
                closedSessions.add(target);
                userSessions.remove(target);
            }
        }

        public void closeExpiredSessions(long currentTime) {
            for (Map.Entry<String, List<Session>> entry : activeSessions.entrySet()) {
                Iterator<Session> it = entry.getValue().iterator();
                while (it.hasNext()) {
                    Session s = it.next();
                    if (currentTime - s.endTime > gapMs) {
                        closedSessions.add(s);
                        it.remove();
                    }
                }
            }
        }

        public List<Session> getClosedSessions() { return closedSessions; }
        public int getActiveSessionCount() {
            return activeSessions.values().stream().mapToInt(List::size).sum();
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Session Window with Gap Detection ===\n");

        // 5 second gap timeout, 30 second max session
        SessionWindowProcessor processor = new SessionWindowProcessor(5000, 30000);

        SessionEvent[] events = {
            new SessionEvent("user1", "page_view", 1000),
            new SessionEvent("user1", "click", 3000),      // same session (gap < 5s)
            new SessionEvent("user1", "scroll", 4500),     // same session
            new SessionEvent("user2", "page_view", 5000),  // user2 session starts
            new SessionEvent("user1", "click", 12000),     // NEW session for user1 (gap > 5s from 4500)
            new SessionEvent("user1", "purchase", 13000),  // same new session
            new SessionEvent("user2", "click", 7000),      // same user2 session
        };

        for (SessionEvent e : events) {
            processor.processEvent(e);
            System.out.printf("Event: %s/%s @%d | Active sessions: %d%n",
                    e.userId, e.action, e.timestamp, processor.getActiveSessionCount());
        }

        // Close expired sessions
        processor.closeExpiredSessions(20000);
        System.out.println("\n--- Closed Sessions (after t=20000) ---");
        processor.getClosedSessions().forEach(System.out::println);
        System.out.println("Remaining active: " + processor.getActiveSessionCount());
    }
}
