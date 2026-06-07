package com.codex.javaconcepts.lld;

import java.util.EnumMap;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class ValueObjectExamples {
    public static void main(String[] args) {
        recordValueObject();
        immutableClass();
        enumCollections();
        sealedType();
    }

    private static void recordValueObject() {
        UserId id1 = new UserId("u1");
        UserId id2 = new UserId("u1");
        System.out.println("Record value equality: " + id1.equals(id2));
        System.out.println("Record toString: " + id1);
    }

    private static void immutableClass() {
        Money first = new Money("INR", 100);
        Money second = new Money("INR", 50);
        System.out.println("Immutable Money add: " + first.add(second));

        Team team = new Team(List.of("Asha", "Ravi"));
        System.out.println("Defensive copied team members: " + team.members());
    }

    private static void enumCollections() {
        EnumSet<OrderStatus> terminal = EnumSet.of(OrderStatus.CANCELLED, OrderStatus.DELIVERED);
        EnumMap<OrderStatus, String> labels = new EnumMap<>(OrderStatus.class);
        labels.put(OrderStatus.CREATED, "Created");
        labels.put(OrderStatus.PAID, "Paid");

        System.out.println("EnumSet terminal states: " + terminal);
        System.out.println("EnumMap labels: " + labels);
    }

    private static void sealedType() {
        List<PaymentCommand> commands = List.of(
            new CardPayment("token-123"),
            new CashPayment()
        );

        for (PaymentCommand command : commands) {
            System.out.println("Payment command: " + describe(command));
        }
    }

    private static String describe(PaymentCommand command) {
        if (command instanceof CardPayment cardPayment) {
            return "card token=" + cardPayment.cardToken();
        }
        if (command instanceof CashPayment) {
            return "cash";
        }
        throw new IllegalStateException("unknown command");
    }

    private record UserId(String value) {
        private UserId {
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException("value is required");
            }
        }
    }

    private static final class Money {
        private final String currency;
        private final long cents;

        private Money(String currency, long cents) {
            this.currency = Objects.requireNonNull(currency, "currency");
            this.cents = cents;
        }

        private Money add(Money other) {
            if (!currency.equals(other.currency)) {
                throw new IllegalArgumentException("currency mismatch");
            }
            return new Money(currency, cents + other.cents);
        }

        public String toString() {
            return currency + " " + cents;
        }
    }

    private static final class Team {
        private final List<String> members;

        private Team(List<String> members) {
            this.members = List.copyOf(members);
        }

        private List<String> members() {
            return members;
        }
    }

    private enum OrderStatus {
        CREATED, PAID, DELIVERED, CANCELLED
    }

    private sealed interface PaymentCommand permits CardPayment, CashPayment {
    }

    private record CardPayment(String cardToken) implements PaymentCommand {
    }

    private record CashPayment() implements PaymentCommand {
    }
}

