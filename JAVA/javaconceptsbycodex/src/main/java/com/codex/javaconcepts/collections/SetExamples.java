package com.codex.javaconcepts.collections;

import java.util.EnumSet;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

public class SetExamples {
    public static void main(String[] args) {
        hashSetBasics();
        linkedHashSetPreservesInsertionOrder();
        treeSetNavigableOperations();
        enumSetExample();
        mutableSetElementPitfall();
    }

    private static void hashSetBasics() {
        Set<String> tags = new HashSet<>();
        System.out.println("add java: " + tags.add("java"));
        System.out.println("add lld: " + tags.add("lld"));
        System.out.println("add duplicate java: " + tags.add("java"));
        System.out.println("HashSet values: " + tags);
        System.out.println("contains lld: " + tags.contains("lld"));

        tags.remove("lld");
        System.out.println("After remove: " + tags);
    }

    private static void linkedHashSetPreservesInsertionOrder() {
        Set<String> ordered = new LinkedHashSet<>();
        ordered.add("third");
        ordered.add("first");
        ordered.add("second");
        ordered.add("first");
        System.out.println("LinkedHashSet insertion order: " + ordered);
    }

    private static void treeSetNavigableOperations() {
        TreeSet<Integer> floors = new TreeSet<>(Set.of(1, 3, 5, 8, 13));
        System.out.println("TreeSet sorted floors: " + floors);
        System.out.println("floor(6): " + floors.floor(6));
        System.out.println("ceiling(6): " + floors.ceiling(6));
        System.out.println("lower(5): " + floors.lower(5));
        System.out.println("higher(5): " + floors.higher(5));
        System.out.println("subSet(3, 10): " + floors.subSet(3, 10));
    }

    private static void enumSetExample() {
        EnumSet<Permission> permissions = EnumSet.of(Permission.READ, Permission.WRITE);
        permissions.add(Permission.DELETE);
        System.out.println("EnumSet permissions: " + permissions);
    }

    private static void mutableSetElementPitfall() {
        Set<MutableUser> users = new HashSet<>();
        MutableUser user = new MutableUser("a@example.com");
        users.add(user);

        System.out.println("Contains before mutation: " + users.contains(user));
        user.email = "changed@example.com";
        System.out.println("Contains after hash field mutation: " + users.contains(user));
    }

    private enum Permission {
        READ, WRITE, DELETE
    }

    private static class MutableUser {
        private String email;

        private MutableUser(String email) {
            this.email = email;
        }

        public boolean equals(Object o) {
            return o instanceof MutableUser other && Objects.equals(email, other.email);
        }

        public int hashCode() {
            return Objects.hash(email);
        }
    }
}

