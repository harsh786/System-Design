import java.util.*;

/**
 * Chain of Responsibility Design Pattern
 * 
 * Allows passing requests along a chain of handlers. Each handler decides
 * either to process the request or pass it to the next handler in the chain.
 */
public class ChainOfResponsibilityPattern {

    // ==================== EXAMPLE 1: Authentication Pipeline ====================

    static class Request {
        private String token;
        private String user;
        private String role;
        private String body;
        private String ip;
        private Map<String, Object> context = new HashMap<>();

        public Request(String token, String user, String role, String body, String ip) {
            this.token = token;
            this.user = user;
            this.role = role;
            this.body = body;
            this.ip = ip;
        }

        public String getToken() { return token; }
        public String getUser() { return user; }
        public String getRole() { return role; }
        public String getBody() { return body; }
        public String getIp() { return ip; }
        public Map<String, Object> getContext() { return context; }

        @Override
        public String toString() {
            return String.format("Request[user=%s, role=%s, ip=%s]", user, role, ip);
        }
    }

    static class Response {
        private boolean success;
        private String message;

        public Response(boolean success, String message) {
            this.success = success;
            this.message = message;
        }

        public boolean isSuccess() { return success; }
        public String getMessage() { return message; }

        @Override
        public String toString() {
            return (success ? "SUCCESS" : "FAILED") + ": " + message;
        }
    }

    // Handler interface
    interface Handler {
        Handler setNext(Handler next);
        Response handle(Request request);
    }

    // Abstract base handler with default chaining logic
    static abstract class BaseHandler implements Handler {
        private Handler next;

        @Override
        public Handler setNext(Handler next) {
            this.next = next;
            return next; // allows fluent chaining
        }

        @Override
        public Response handle(Request request) {
            if (next != null) {
                return next.handle(request);
            }
            return new Response(true, "Request passed all handlers");
        }

        protected Response passToNext(Request request) {
            return super.getClass() != null ? handle(request) : null;
            // Actually delegate to base handle which calls next
        }

        protected Handler getNext() { return next; }

        protected Response forward(Request request) {
            if (next != null) {
                return next.handle(request);
            }
            return new Response(true, "End of chain - request fully processed");
        }
    }

    // Concrete Handler 1: Rate Limiting
    static class RateLimitHandler extends BaseHandler {
        private Map<String, Integer> requestCounts = new HashMap<>();
        private static final int MAX_REQUESTS = 5;

        @Override
        public Response handle(Request request) {
            System.out.println("  [RateLimitHandler] Checking rate limit for IP: " + request.getIp());
            int count = requestCounts.getOrDefault(request.getIp(), 0);
            if (count >= MAX_REQUESTS) {
                return new Response(false, "Rate limit exceeded for IP: " + request.getIp());
            }
            requestCounts.put(request.getIp(), count + 1);
            return forward(request);
        }
    }

    // Concrete Handler 2: Authentication
    static class AuthenticationHandler extends BaseHandler {
        private static final Set<String> VALID_TOKENS = Set.of("token-abc", "token-xyz", "token-admin");

        @Override
        public Response handle(Request request) {
            System.out.println("  [AuthenticationHandler] Verifying token: " + request.getToken());
            if (request.getToken() == null || !VALID_TOKENS.contains(request.getToken())) {
                return new Response(false, "Authentication failed - invalid token");
            }
            request.getContext().put("authenticated", true);
            return forward(request);
        }
    }

    // Concrete Handler 3: Authorization
    static class AuthorizationHandler extends BaseHandler {
        private String requiredRole;

        public AuthorizationHandler(String requiredRole) {
            this.requiredRole = requiredRole;
        }

        @Override
        public Response handle(Request request) {
            System.out.println("  [AuthorizationHandler] Checking role: " + request.getRole() + " against required: " + requiredRole);
            if (!request.getRole().equals(requiredRole) && !request.getRole().equals("admin")) {
                return new Response(false, "Authorization failed - requires role: " + requiredRole);
            }
            return forward(request);
        }
    }

    // Concrete Handler 4: Validation
    static class ValidationHandler extends BaseHandler {
        @Override
        public Response handle(Request request) {
            System.out.println("  [ValidationHandler] Validating request body");
            if (request.getBody() == null || request.getBody().trim().isEmpty()) {
                return new Response(false, "Validation failed - empty request body");
            }
            if (request.getBody().length() > 1000) {
                return new Response(false, "Validation failed - body too large");
            }
            return forward(request);
        }
    }

    // Concrete Handler 5: Business Logic
    static class BusinessLogicHandler extends BaseHandler {
        @Override
        public Response handle(Request request) {
            System.out.println("  [BusinessLogicHandler] Processing business logic for: " + request.getUser());
            return new Response(true, "Request processed successfully for user: " + request.getUser());
        }
    }

    // ==================== EXAMPLE 2: Support Ticket Escalation ====================

    static class Ticket {
        enum Priority { LOW, MEDIUM, HIGH, CRITICAL }

        private String id;
        private String description;
        private Priority priority;
        private int complexity; // 1-10

        public Ticket(String id, String description, Priority priority, int complexity) {
            this.id = id;
            this.description = description;
            this.priority = priority;
            this.complexity = complexity;
        }

        public String getId() { return id; }
        public String getDescription() { return description; }
        public Priority getPriority() { return priority; }
        public int getComplexity() { return complexity; }
    }

    interface SupportHandler {
        SupportHandler setNext(SupportHandler next);
        String handle(Ticket ticket);
    }

    static abstract class BaseSupportHandler implements SupportHandler {
        private SupportHandler next;
        protected String name;

        public BaseSupportHandler(String name) { this.name = name; }

        @Override
        public SupportHandler setNext(SupportHandler next) {
            this.next = next;
            return next;
        }

        protected String escalate(Ticket ticket) {
            if (next != null) {
                System.out.println("    " + name + " escalating ticket " + ticket.getId() + " to next level");
                return next.handle(ticket);
            }
            return name + ": No further escalation possible. Ticket " + ticket.getId() + " queued for review.";
        }
    }

    static class Level1Support extends BaseSupportHandler {
        public Level1Support() { super("Level1Support"); }

        @Override
        public String handle(Ticket ticket) {
            if (ticket.getComplexity() <= 3 && ticket.getPriority() == Ticket.Priority.LOW) {
                System.out.println("    " + name + " resolved ticket " + ticket.getId());
                return name + " resolved: " + ticket.getDescription();
            }
            return escalate(ticket);
        }
    }

    static class Level2Support extends BaseSupportHandler {
        public Level2Support() { super("Level2Support"); }

        @Override
        public String handle(Ticket ticket) {
            if (ticket.getComplexity() <= 6 && ticket.getPriority().ordinal() <= Ticket.Priority.MEDIUM.ordinal()) {
                System.out.println("    " + name + " resolved ticket " + ticket.getId());
                return name + " resolved: " + ticket.getDescription();
            }
            return escalate(ticket);
        }
    }

    static class ManagerSupport extends BaseSupportHandler {
        public ManagerSupport() { super("ManagerSupport"); }

        @Override
        public String handle(Ticket ticket) {
            if (ticket.getComplexity() <= 8 && ticket.getPriority().ordinal() <= Ticket.Priority.HIGH.ordinal()) {
                System.out.println("    " + name + " resolved ticket " + ticket.getId());
                return name + " resolved: " + ticket.getDescription();
            }
            return escalate(ticket);
        }
    }

    static class DirectorSupport extends BaseSupportHandler {
        public DirectorSupport() { super("DirectorSupport"); }

        @Override
        public String handle(Ticket ticket) {
            System.out.println("    " + name + " handling critical ticket " + ticket.getId());
            return name + " resolved (executive action): " + ticket.getDescription();
        }
    }

    // ==================== EXAMPLE 3: Logging Framework ====================

    enum LogLevel { DEBUG(1), INFO(2), WARNING(3), ERROR(4), FATAL(5);
        final int severity;
        LogLevel(int severity) { this.severity = severity; }
    }

    static class LogMessage {
        private LogLevel level;
        private String message;
        private String timestamp;

        public LogMessage(LogLevel level, String message) {
            this.level = level;
            this.message = message;
            this.timestamp = new Date().toString();
        }

        public LogLevel getLevel() { return level; }
        public String getMessage() { return message; }
        public String getTimestamp() { return timestamp; }
    }

    static abstract class Logger {
        private LogLevel level;
        private Logger next;

        public Logger(LogLevel level) { this.level = level; }

        public Logger setNext(Logger next) {
            this.next = next;
            return next;
        }

        public void log(LogMessage message) {
            if (message.getLevel().severity >= this.level.severity) {
                write(message);
            }
            if (next != null) {
                next.log(message);
            }
        }

        protected abstract void write(LogMessage message);
    }

    static class DebugLogger extends Logger {
        public DebugLogger() { super(LogLevel.DEBUG); }

        @Override
        protected void write(LogMessage msg) {
            System.out.println("    [DEBUG-FILE] " + msg.getLevel() + ": " + msg.getMessage());
        }
    }

    static class InfoLogger extends Logger {
        public InfoLogger() { super(LogLevel.INFO); }

        @Override
        protected void write(LogMessage msg) {
            System.out.println("    [INFO-CONSOLE] " + msg.getLevel() + ": " + msg.getMessage());
        }
    }

    static class ErrorLogger extends Logger {
        public ErrorLogger() { super(LogLevel.ERROR); }

        @Override
        protected void write(LogMessage msg) {
            System.out.println("    [ERROR-ALERT] " + msg.getLevel() + ": " + msg.getMessage() + " >>> ALERT SENT!");
        }
    }

    // ==================== MAIN ====================

    public static void main(String[] args) {
        System.out.println("╔══════════════════════════════════════════════════════════════╗");
        System.out.println("║        CHAIN OF RESPONSIBILITY DESIGN PATTERN               ║");
        System.out.println("╚══════════════════════════════════════════════════════════════╝\n");

        // === Example 1: Authentication Pipeline ===
        System.out.println("═══ Example 1: Authentication Pipeline ═══\n");

        RateLimitHandler rateLimit = new RateLimitHandler();
        AuthenticationHandler auth = new AuthenticationHandler();
        AuthorizationHandler authz = new AuthorizationHandler("editor");
        ValidationHandler validation = new ValidationHandler();
        BusinessLogicHandler business = new BusinessLogicHandler();

        rateLimit.setNext(auth);
        auth.setNext(authz);
        authz.setNext(validation);
        validation.setNext(business);

        // Test 1: Valid request passes all handlers
        System.out.println("--- Test 1: Valid request (should pass all) ---");
        Request req1 = new Request("token-abc", "alice", "editor", "update article", "192.168.1.1");
        System.out.println("Result: " + rateLimit.handle(req1) + "\n");

        // Test 2: Invalid token - stops at authentication
        System.out.println("--- Test 2: Invalid token (stops at auth) ---");
        Request req2 = new Request("invalid-token", "bob", "editor", "delete stuff", "192.168.1.2");
        System.out.println("Result: " + rateLimit.handle(req2) + "\n");

        // Test 3: Wrong role - stops at authorization
        System.out.println("--- Test 3: Wrong role (stops at authorization) ---");
        Request req3 = new Request("token-xyz", "charlie", "viewer", "edit content", "192.168.1.3");
        System.out.println("Result: " + rateLimit.handle(req3) + "\n");

        // Test 4: Empty body - stops at validation
        System.out.println("--- Test 4: Empty body (stops at validation) ---");
        Request req4 = new Request("token-admin", "dave", "admin", "", "192.168.1.4");
        System.out.println("Result: " + rateLimit.handle(req4) + "\n");

        // === Example 2: Support Ticket Escalation ===
        System.out.println("\n═══ Example 2: Support Ticket Escalation ═══\n");

        Level1Support l1 = new Level1Support();
        Level2Support l2 = new Level2Support();
        ManagerSupport mgr = new ManagerSupport();
        DirectorSupport dir = new DirectorSupport();

        l1.setNext(l2);
        l2.setNext(mgr);
        mgr.setNext(dir);

        Ticket[] tickets = {
            new Ticket("T-001", "Password reset", Ticket.Priority.LOW, 1),
            new Ticket("T-002", "Database connection issue", Ticket.Priority.MEDIUM, 5),
            new Ticket("T-003", "Production outage", Ticket.Priority.HIGH, 7),
            new Ticket("T-004", "Security breach detected", Ticket.Priority.CRITICAL, 10),
        };

        for (Ticket t : tickets) {
            System.out.println("  Processing: [" + t.getId() + "] " + t.getDescription()
                + " (Priority: " + t.getPriority() + ", Complexity: " + t.getComplexity() + ")");
            String result = l1.handle(t);
            System.out.println("  Result: " + result + "\n");
        }

        // === Example 3: Logging Framework ===
        System.out.println("\n═══ Example 3: Logging Framework ═══\n");

        DebugLogger debugLogger = new DebugLogger();
        InfoLogger infoLogger = new InfoLogger();
        ErrorLogger errorLogger = new ErrorLogger();

        // Chain: debug -> info -> error (each handles messages at its level or above)
        debugLogger.setNext(infoLogger);
        infoLogger.setNext(errorLogger);

        System.out.println("  Logging DEBUG message:");
        debugLogger.log(new LogMessage(LogLevel.DEBUG, "Variable x = 42"));

        System.out.println("\n  Logging INFO message:");
        debugLogger.log(new LogMessage(LogLevel.INFO, "User logged in"));

        System.out.println("\n  Logging ERROR message:");
        debugLogger.log(new LogMessage(LogLevel.ERROR, "NullPointerException in PaymentService"));

        System.out.println("\n  Logging FATAL message:");
        debugLogger.log(new LogMessage(LogLevel.FATAL, "System out of memory - shutting down"));

        System.out.println("\n═══ Pattern Summary ═══");
        System.out.println("• Requests flow through the chain until handled or chain ends");
        System.out.println("• Each handler is independent and doesn't know the full chain");
        System.out.println("• Handlers can be added/removed/reordered without changing others");
        System.out.println("• Decouples sender from receiver of a request");
    }
}
