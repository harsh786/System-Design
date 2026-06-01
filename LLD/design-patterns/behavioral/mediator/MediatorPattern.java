import java.util.*;

/**
 * Mediator Design Pattern - Complete Implementation
 * 
 * The Mediator pattern defines an object that encapsulates how a set of objects interact.
 * Objects no longer communicate directly with each other, but instead communicate through the mediator.
 */
public class MediatorPattern {

    // ==================== EXAMPLE 1: Chat Room ====================

    interface ChatMediator {
        void sendMessage(String message, User sender);
        void addUser(User user);
    }

    static abstract class User {
        protected ChatMediator mediator;
        protected String name;
        protected String role;

        public User(ChatMediator mediator, String name, String role) {
            this.mediator = mediator;
            this.name = name;
            this.role = role;
        }

        public String getName() { return name; }
        public String getRole() { return role; }

        public void send(String message) {
            System.out.println(role + " [" + name + "] sends: " + message);
            mediator.sendMessage(message, this);
        }

        public abstract void receive(String message, User sender);
    }

    static class RegularUser extends User {
        public RegularUser(ChatMediator mediator, String name) {
            super(mediator, name, "Regular");
        }

        @Override
        public void receive(String message, User sender) {
            System.out.println("  " + name + " received from " + sender.getName() + ": " + message);
        }
    }

    static class PremiumUser extends User {
        public PremiumUser(ChatMediator mediator, String name) {
            super(mediator, name, "Premium");
        }

        @Override
        public void receive(String message, User sender) {
            System.out.println("  [P] " + name + " received from " + sender.getName() + ": " + message);
        }
    }

    static class AdminUser extends User {
        public AdminUser(ChatMediator mediator, String name) {
            super(mediator, name, "Admin");
        }

        @Override
        public void receive(String message, User sender) {
            System.out.println("  [ADMIN] " + name + " received from " + sender.getName() + ": " + message);
        }

        public void broadcast(String message) {
            System.out.println("Admin [" + name + "] broadcasts: " + message);
            mediator.sendMessage("[BROADCAST] " + message, this);
        }
    }

    static class ChatRoom implements ChatMediator {
        private List<User> users = new ArrayList<>();

        @Override
        public void addUser(User user) {
            users.add(user);
            System.out.println(">> " + user.getName() + " (" + user.getRole() + ") joined the chat room");
        }

        @Override
        public void sendMessage(String message, User sender) {
            for (User user : users) {
                if (user != sender) {
                    user.receive(message, sender);
                }
            }
        }
    }

    // ==================== EXAMPLE 2: Air Traffic Control ====================

    interface ATCMediator {
        void registerAircraft(Aircraft aircraft);
        void requestLanding(Aircraft aircraft);
        void requestTakeoff(Aircraft aircraft);
        void notifyAll(String message, Aircraft source);
    }

    static abstract class Aircraft {
        protected ATCMediator atc;
        protected String callSign;
        protected boolean onGround;

        public Aircraft(ATCMediator atc, String callSign) {
            this.atc = atc;
            this.callSign = callSign;
            this.onGround = false;
        }

        public String getCallSign() { return callSign; }
        public boolean isOnGround() { return onGround; }
        public void setOnGround(boolean onGround) { this.onGround = onGround; }

        public void requestLanding() {
            System.out.println(callSign + " requests landing.");
            atc.requestLanding(this);
        }

        public void requestTakeoff() {
            System.out.println(callSign + " requests takeoff.");
            atc.requestTakeoff(this);
        }

        public abstract void receiveMessage(String message);
    }

    static class CommercialFlight extends Aircraft {
        public CommercialFlight(ATCMediator atc, String callSign) {
            super(atc, callSign);
        }

        @Override
        public void receiveMessage(String message) {
            System.out.println("  [Commercial] " + callSign + " received: " + message);
        }
    }

    static class PrivateJet extends Aircraft {
        public PrivateJet(ATCMediator atc, String callSign) {
            super(atc, callSign);
        }

        @Override
        public void receiveMessage(String message) {
            System.out.println("  [Private] " + callSign + " received: " + message);
        }
    }

    static class AirTrafficControl implements ATCMediator {
        private List<Aircraft> aircraft = new ArrayList<>();
        private boolean runwayFree = true;

        @Override
        public void registerAircraft(Aircraft a) {
            aircraft.add(a);
            System.out.println(">> ATC registered: " + a.getCallSign());
        }

        @Override
        public void requestLanding(Aircraft a) {
            if (runwayFree) {
                runwayFree = false;
                a.setOnGround(true);
                a.receiveMessage("Landing cleared. Runway assigned.");
                notifyAll(a.getCallSign() + " is landing. Hold positions.", a);
            } else {
                a.receiveMessage("Landing denied. Runway occupied. Enter holding pattern.");
            }
        }

        @Override
        public void requestTakeoff(Aircraft a) {
            if (runwayFree) {
                runwayFree = false;
                a.receiveMessage("Takeoff cleared. Runway assigned.");
                notifyAll(a.getCallSign() + " is taking off. Hold positions.", a);
                // After takeoff, runway is free again
                runwayFree = true;
                a.setOnGround(false);
            } else {
                a.receiveMessage("Takeoff denied. Runway occupied. Hold position.");
            }
        }

        @Override
        public void notifyAll(String message, Aircraft source) {
            for (Aircraft a : aircraft) {
                if (a != source) {
                    a.receiveMessage("ATC: " + message);
                }
            }
        }

        public void freeRunway() {
            runwayFree = true;
            System.out.println(">> ATC: Runway is now free.");
            notifyAll("Runway is now free.", null);
        }
    }

    // ==================== EXAMPLE 3: UI Form Mediator ====================

    interface DialogMediator {
        void notify(Component sender, String event);
    }

    static abstract class Component {
        protected DialogMediator dialog;
        protected String name;

        public Component(DialogMediator dialog, String name) {
            this.dialog = dialog;
            this.name = name;
        }

        public String getName() { return name; }
    }

    static class TextField extends Component {
        private String text = "";

        public TextField(DialogMediator dialog, String name) {
            super(dialog, name);
        }

        public void setText(String text) {
            this.text = text;
            System.out.println("TextField[" + name + "] text set to: \"" + text + "\"");
            dialog.notify(this, "textChanged");
        }

        public String getText() { return text; }
        public boolean isEmpty() { return text.isEmpty(); }
    }

    static class Checkbox extends Component {
        private boolean checked = false;

        public Checkbox(DialogMediator dialog, String name) {
            super(dialog, name);
        }

        public void toggle() {
            checked = !checked;
            System.out.println("Checkbox[" + name + "] toggled to: " + checked);
            dialog.notify(this, "toggled");
        }

        public boolean isChecked() { return checked; }
    }

    static class Button extends Component {
        private boolean enabled = false;

        public Button(DialogMediator dialog, String name) {
            super(dialog, name);
        }

        public void click() {
            if (enabled) {
                System.out.println("Button[" + name + "] clicked!");
                dialog.notify(this, "clicked");
            } else {
                System.out.println("Button[" + name + "] is disabled, cannot click.");
            }
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
            System.out.println("  -> Button[" + name + "] " + (enabled ? "ENABLED" : "DISABLED"));
        }

        public boolean isEnabled() { return enabled; }
    }

    static class RegistrationFormMediator implements DialogMediator {
        private TextField usernameField;
        private TextField emailField;
        private Checkbox termsCheckbox;
        private Button submitButton;

        public void setComponents(TextField username, TextField email, Checkbox terms, Button submit) {
            this.usernameField = username;
            this.emailField = email;
            this.termsCheckbox = terms;
            this.submitButton = submit;
        }

        @Override
        public void notify(Component sender, String event) {
            // Complex coordination logic lives here, not in components
            if (event.equals("textChanged") || event.equals("toggled")) {
                validateForm();
            } else if (event.equals("clicked") && sender == submitButton) {
                System.out.println("  -> Form submitted with username: \"" + usernameField.getText()
                        + "\", email: \"" + emailField.getText() + "\"");
            }
        }

        private void validateForm() {
            boolean valid = !usernameField.isEmpty()
                    && !emailField.isEmpty()
                    && emailField.getText().contains("@")
                    && termsCheckbox.isChecked();
            submitButton.setEnabled(valid);
        }
    }

    // ==================== MAIN ====================

    public static void main(String[] args) {
        System.out.println("=".repeat(60));
        System.out.println("MEDIATOR DESIGN PATTERN DEMO");
        System.out.println("=".repeat(60));

        // --- Example 1: Chat Room ---
        System.out.println("\n--- Example 1: Chat Room Mediator ---\n");
        ChatRoom chatRoom = new ChatRoom();

        User alice = new RegularUser(chatRoom, "Alice");
        User bob = new PremiumUser(chatRoom, "Bob");
        AdminUser charlie = new AdminUser(chatRoom, "Charlie");

        chatRoom.addUser(alice);
        chatRoom.addUser(bob);
        chatRoom.addUser(charlie);

        System.out.println();
        alice.send("Hello everyone!");
        System.out.println();
        bob.send("Hey Alice!");
        System.out.println();
        charlie.broadcast("Server maintenance at midnight.");

        // --- Example 2: Air Traffic Control ---
        System.out.println("\n--- Example 2: Air Traffic Control Mediator ---\n");
        AirTrafficControl atc = new AirTrafficControl();

        Aircraft flight1 = new CommercialFlight(atc, "AA-101");
        Aircraft flight2 = new CommercialFlight(atc, "UA-202");
        Aircraft jet1 = new PrivateJet(atc, "PJ-007");

        atc.registerAircraft(flight1);
        atc.registerAircraft(flight2);
        atc.registerAircraft(jet1);

        System.out.println();
        flight1.requestLanding();
        System.out.println();
        flight2.requestLanding(); // should be denied
        System.out.println();
        atc.freeRunway();
        System.out.println();
        jet1.requestTakeoff();

        // --- Example 3: UI Form Mediator ---
        System.out.println("\n--- Example 3: UI Form Dialog Mediator ---\n");
        RegistrationFormMediator formMediator = new RegistrationFormMediator();

        TextField username = new TextField(formMediator, "username");
        TextField email = new TextField(formMediator, "email");
        Checkbox terms = new Checkbox(formMediator, "agreeTerms");
        Button submit = new Button(formMediator, "submit");

        formMediator.setComponents(username, email, terms, submit);

        submit.click(); // disabled
        System.out.println();
        username.setText("john_doe");
        email.setText("john");        // invalid email
        terms.toggle();               // checked but email invalid
        System.out.println();
        email.setText("john@example.com"); // now valid
        System.out.println();
        submit.click(); // should work now

        System.out.println("\n" + "=".repeat(60));
        System.out.println("Key Insight: Objects never communicate directly.");
        System.out.println("All coordination flows through the mediator.");
        System.out.println("=".repeat(60));
    }
}
