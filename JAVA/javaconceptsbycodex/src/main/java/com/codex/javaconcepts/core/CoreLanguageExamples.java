package com.codex.javaconcepts.core;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

public class CoreLanguageExamples {
    public static void main(String[] args) {
        primitivesWrappersAndAutoboxing();
        arraysAndVarargs();
        strings();
        stringBuilder();
        comparableAndComparator();
        javaTime();
    }

    private static void primitivesWrappersAndAutoboxing() {
        int primitive = 10;
        Integer boxed = primitive;
        int unboxed = boxed;

        BigDecimal money = new BigDecimal("10.25");

        System.out.println("primitive=" + primitive + ", boxed=" + boxed + ", unboxed=" + unboxed);
        System.out.println("BigDecimal money example: " + money);
    }

    private static void arraysAndVarargs() {
        int[] numbers = {3, 1, 2};
        Arrays.sort(numbers);
        System.out.println("Sorted array: " + Arrays.toString(numbers));
        System.out.println("Varargs sum: " + sum(1, 2, 3, 4));
    }

    private static int sum(int... values) {
        int total = 0;
        for (int value : values) {
            total += value;
        }
        return total;
    }

    private static void strings() {
        String literalA = "java";
        String literalB = "java";
        String object = new String("java");
        String sentence = "  Java LLD Concepts  ";

        System.out.println("literalA == literalB: " + (literalA == literalB));
        System.out.println("literalA == object: " + (literalA == object));
        System.out.println("literalA.equals(object): " + literalA.equals(object));
        System.out.println("strip/toUpperCase: " + sentence.strip().toUpperCase());
        System.out.println("substring: " + sentence.strip().substring(0, 4));
    }

    private static void stringBuilder() {
        StringBuilder builder = new StringBuilder();
        builder.append("Order");
        builder.append("-");
        builder.append(101);
        System.out.println("StringBuilder result: " + builder);
    }

    private static void comparableAndComparator() {
        List<Version> versions = new ArrayList<>(List.of(
            new Version(2, 0),
            new Version(1, 5),
            new Version(1, 2)
        ));
        versions.sort(Comparator.naturalOrder());
        System.out.println("Comparable versions: " + versions);

        List<User> users = new ArrayList<>(List.of(
            new User("Asha", 30),
            new User("Ravi", 25),
            new User("Meera", 30)
        ));
        users.sort(Comparator.comparing(User::age).thenComparing(User::name));
        System.out.println("Comparator users: " + users);
    }

    private static void javaTime() {
        Instant now = Instant.now();
        LocalDate today = LocalDate.now();
        Duration ttl = Duration.ofMinutes(15);

        System.out.println("Instant now: " + now);
        System.out.println("LocalDate today: " + today);
        System.out.println("TTL seconds: " + ttl.toSeconds());
    }

    private record Version(int major, int minor) implements Comparable<Version> {
        public int compareTo(Version other) {
            int byMajor = Integer.compare(major, other.major);
            return byMajor != 0 ? byMajor : Integer.compare(minor, other.minor);
        }
    }

    private record User(String name, int age) {
    }
}

