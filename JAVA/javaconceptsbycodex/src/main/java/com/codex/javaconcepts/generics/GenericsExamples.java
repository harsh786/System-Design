package com.codex.javaconcepts.generics;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public class GenericsExamples {
    public static void main(String[] args) {
        genericClass();
        genericMethod();
        boundedTypeParameter();
        wildcardProducerExtends();
        wildcardConsumerSuper();
        genericRepository();
    }

    private static void genericClass() {
        Box<String> box = new Box<>();
        box.put("java");
        String value = box.get();
        System.out.println("Generic Box value: " + value);
    }

    private static void genericMethod() {
        String firstName = first(List.of("Asha", "Ravi"));
        Integer firstNumber = first(List.of(10, 20));
        System.out.println("Generic method firstName: " + firstName);
        System.out.println("Generic method firstNumber: " + firstNumber);
    }

    private static void boundedTypeParameter() {
        System.out.println("max: " + max(List.of(4, 10, 7)));
    }

    private static void wildcardProducerExtends() {
        List<Integer> integers = List.of(1, 2, 3);
        List<Double> doubles = List.of(1.5, 2.5);
        System.out.println("total integers: " + total(integers));
        System.out.println("total doubles: " + total(doubles));
    }

    private static void wildcardConsumerSuper() {
        List<Number> numbers = new ArrayList<>();
        addIntegers(numbers);
        System.out.println("Consumer super numbers: " + numbers);
    }

    private static void genericRepository() {
        Repository<User, UserId> repository = new InMemoryRepository<>();
        UserId id = new UserId("u1");
        repository.save(id, new User(id, "asha@example.com"));
        Optional<User> found = repository.findById(id);
        System.out.println("Repository found: " + found.orElseThrow());
    }

    private static <T> T first(List<T> values) {
        if (values.isEmpty()) {
            throw new IllegalArgumentException("empty list");
        }
        return values.get(0);
    }

    private static <T extends Comparable<T>> T max(List<T> values) {
        T best = values.get(0);
        for (T value : values) {
            if (value.compareTo(best) > 0) {
                best = value;
            }
        }
        return best;
    }

    private static double total(List<? extends Number> numbers) {
        double sum = 0;
        for (Number number : numbers) {
            sum += number.doubleValue();
        }
        return sum;
    }

    private static void addIntegers(List<? super Integer> values) {
        values.add(1);
        values.add(2);
    }

    private static class Box<T> {
        private T value;

        void put(T value) {
            this.value = value;
        }

        T get() {
            return value;
        }
    }

    private interface Repository<T, ID> {
        void save(ID id, T value);
        Optional<T> findById(ID id);
    }

    private static class InMemoryRepository<T, ID> implements Repository<T, ID> {
        private final Map<ID, T> values = new HashMap<>();

        public void save(ID id, T value) {
            values.put(id, value);
        }

        public Optional<T> findById(ID id) {
            return Optional.ofNullable(values.get(id));
        }
    }

    private record UserId(String value) {
    }

    private record User(UserId id, String email) {
    }
}

