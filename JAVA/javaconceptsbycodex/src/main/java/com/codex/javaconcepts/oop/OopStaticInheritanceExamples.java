package com.codex.javaconcepts.oop;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public class OopStaticInheritanceExamples {
    public static void main(String[] args) {
        staticFieldsAndMethods();
        staticNestedBuilder();
        innerClassExample();
        inheritanceAndPolymorphism();
        compositionExample();
        overloadAndOverride();
    }

    private static void staticFieldsAndMethods() {
        System.out.println("GST on 1000 paise: " + MoneyUtil.gst(1000));
        System.out.println("Generated ID: " + IdGenerator.next());
        System.out.println("Generated ID: " + IdGenerator.next());
    }

    private static void staticNestedBuilder() {
        User user = new User.Builder()
            .id("u1")
            .email("asha@example.com")
            .displayName("Asha")
            .build();

        System.out.println("User built with static nested Builder: " + user);
    }

    private static void innerClassExample() {
        ShoppingCart cart = new ShoppingCart();
        cart.add("book");
        cart.add("pen");

        ShoppingCart.CartSummary summary = cart.new CartSummary();
        System.out.println("Inner class can read outer object state: " + summary.itemCount());
    }

    private static void inheritanceAndPolymorphism() {
        List<Vehicle> vehicles = List.of(new Bike("KA-BIKE"), new Car("KA-CAR"));
        for (Vehicle vehicle : vehicles) {
            System.out.println(vehicle.numberPlate() + " wheels=" + vehicle.wheels());
        }

        List<NotificationSender> senders = List.of(new EmailSender(), new SmsSender());
        for (NotificationSender sender : senders) {
            sender.send("Order shipped");
        }
    }

    private static void compositionExample() {
        PaymentService service = new PaymentService(new CardPaymentGateway());
        System.out.println(service.pay(500));
    }

    private static void overloadAndOverride() {
        Printer printer = new Printer();
        printer.print("hello");
        printer.print("hello", 2);

        Animal animal = new Dog();
        animal.speak();
    }

    private static class MoneyUtil {
        private static final double GST_RATE = 0.18;

        private static long gst(long paise) {
            return Math.round(paise * GST_RATE);
        }
    }

    private static class IdGenerator {
        private static long next = 1;

        private static long next() {
            return next++;
        }
    }

    private static final class User {
        private final String id;
        private final String email;
        private final String displayName;

        private User(Builder builder) {
            this.id = Objects.requireNonNull(builder.id, "id");
            this.email = Objects.requireNonNull(builder.email, "email");
            this.displayName = builder.displayName == null ? builder.email : builder.displayName;
        }

        public String toString() {
            return "User{id='" + id + "', email='" + email + "', displayName='" + displayName + "'}";
        }

        static class Builder {
            private String id;
            private String email;
            private String displayName;

            Builder id(String id) {
                this.id = id;
                return this;
            }

            Builder email(String email) {
                this.email = email;
                return this;
            }

            Builder displayName(String displayName) {
                this.displayName = displayName;
                return this;
            }

            User build() {
                return new User(this);
            }
        }
    }

    private static class ShoppingCart {
        private final List<String> items = new ArrayList<>();

        void add(String item) {
            items.add(item);
        }

        class CartSummary {
            int itemCount() {
                return items.size();
            }
        }
    }

    private abstract static class Vehicle {
        private final String numberPlate;

        Vehicle(String numberPlate) {
            this.numberPlate = numberPlate;
        }

        String numberPlate() {
            return numberPlate;
        }

        abstract int wheels();
    }

    private static class Bike extends Vehicle {
        Bike(String numberPlate) {
            super(numberPlate);
        }

        int wheels() {
            return 2;
        }
    }

    private static class Car extends Vehicle {
        Car(String numberPlate) {
            super(numberPlate);
        }

        int wheels() {
            return 4;
        }
    }

    private interface NotificationSender {
        void send(String message);
    }

    private static class EmailSender implements NotificationSender {
        public void send(String message) {
            System.out.println("Email sender: " + message);
        }
    }

    private static class SmsSender implements NotificationSender {
        public void send(String message) {
            System.out.println("SMS sender: " + message);
        }
    }

    private interface PaymentGateway {
        boolean charge(long paise);
    }

    private static class CardPaymentGateway implements PaymentGateway {
        public boolean charge(long paise) {
            return paise > 0;
        }
    }

    private static class PaymentService {
        private final PaymentGateway gateway;

        PaymentService(PaymentGateway gateway) {
            this.gateway = gateway;
        }

        String pay(long paise) {
            return gateway.charge(paise) ? "Payment successful" : "Payment failed";
        }
    }

    private static class Printer {
        void print(String text) {
            System.out.println("print one: " + text);
        }

        void print(String text, int copies) {
            System.out.println("print copies=" + copies + ": " + text);
        }
    }

    private static class Animal {
        void speak() {
            System.out.println("animal sound");
        }
    }

    private static class Dog extends Animal {
        @Override
        void speak() {
            System.out.println("dog barks");
        }
    }
}

