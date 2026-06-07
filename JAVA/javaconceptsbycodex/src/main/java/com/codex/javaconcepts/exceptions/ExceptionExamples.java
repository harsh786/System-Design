package com.codex.javaconcepts.exceptions;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.StringReader;

public class ExceptionExamples {
    public static void main(String[] args) throws IOException {
        validationException();
        domainException();
        tryCatchFinally();
        tryWithResources();
    }

    private static void validationException() {
        try {
            createUser("");
        } catch (IllegalArgumentException ex) {
            System.out.println("Caught validation exception: " + ex.getMessage());
        }
    }

    private static void domainException() {
        Wallet wallet = new Wallet("w1", 100);
        try {
            wallet.debit(150);
        } catch (InsufficientBalanceException ex) {
            System.out.println("Caught domain exception: " + ex.getMessage());
        }
    }

    private static void tryCatchFinally() {
        try {
            System.out.println("Processing order");
        } catch (RuntimeException ex) {
            System.out.println("Handle failure");
        } finally {
            System.out.println("finally: record attempt metric");
        }
    }

    private static void tryWithResources() throws IOException {
        try (BufferedReader reader = new BufferedReader(new StringReader("first line\nsecond line"))) {
            System.out.println("try-with-resources read: " + reader.readLine());
        }
    }

    private static User createUser(String email) {
        if (email == null || email.isBlank()) {
            throw new IllegalArgumentException("email is required");
        }
        return new User(email);
    }

    private record User(String email) {
    }

    private static class Wallet {
        private final String id;
        private int balance;

        private Wallet(String id, int balance) {
            this.id = id;
            this.balance = balance;
        }

        private void debit(int amount) {
            if (amount > balance) {
                throw new InsufficientBalanceException(id, balance, amount);
            }
            balance -= amount;
        }
    }

    private static class InsufficientBalanceException extends RuntimeException {
        private InsufficientBalanceException(String walletId, int available, int requested) {
            super("wallet " + walletId + " has " + available + " but requested " + requested);
        }
    }
}

