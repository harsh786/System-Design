package com.codex.javaconcepts.streams;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class StreamsExamples {
    public static void main(String[] args) {
        List<User> users = List.of(
            new User("u1", "Asha", "Delhi", 30),
            new User("u2", "Ravi", "Delhi", 25),
            new User("u3", "Meera", "Mumbai", 35),
            new User("u4", "Kabir", "Bengaluru", 28)
        );

        lambdaAndFunctionalInterfaces();
        streamFilterMapSort(users);
        collectors(users);
        optional(users);
        reduceAndFlatMap();
    }

    private static void lambdaAndFunctionalInterfaces() {
        Predicate<String> nonBlank = text -> text != null && !text.isBlank();
        Function<String, Integer> length = String::length;

        System.out.println("Predicate nonBlank: " + nonBlank.test("java"));
        System.out.println("Function length: " + length.apply("java"));
    }

    private static void streamFilterMapSort(List<User> users) {
        List<String> names = users.stream()
            .filter(user -> user.age() >= 28)
            .sorted(Comparator.comparing(User::age).reversed())
            .map(User::name)
            .toList();

        System.out.println("Users age >= 28 sorted desc: " + names);
    }

    private static void collectors(List<User> users) {
        Map<String, List<User>> usersByCity = users.stream()
            .collect(Collectors.groupingBy(User::city));

        Map<String, Long> countByCity = users.stream()
            .collect(Collectors.groupingBy(User::city, Collectors.counting()));

        String csv = users.stream()
            .map(User::name)
            .collect(Collectors.joining(", "));

        System.out.println("groupingBy city: " + usersByCity);
        System.out.println("counting by city: " + countByCity);
        System.out.println("joining names: " + csv);
    }

    private static void optional(List<User> users) {
        Optional<User> found = users.stream()
            .filter(user -> user.id().equals("u2"))
            .findFirst();

        String display = found
            .map(User::name)
            .orElse("Guest");

        System.out.println("Optional mapped name: " + display);
    }

    private static void reduceAndFlatMap() {
        int total = List.of(1, 2, 3, 4).stream()
            .reduce(0, Integer::sum);

        List<String> words = List.of(
                List.of("java", "collections"),
                List.of("lld", "concurrency")
            ).stream()
            .flatMap(List::stream)
            .toList();

        System.out.println("reduce total: " + total);
        System.out.println("flatMap words: " + words);
    }

    private record User(String id, String name, String city, int age) {
    }
}

