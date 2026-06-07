package com.codex.javaconcepts.collections;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.ConcurrentHashMap;

public class MapExamples {
    public static void main(String[] args) {
        hashMapBasics();
        computeAndMerge();
        linkedHashMapLru();
        treeMapNavigableOperations();
        concurrentHashMapBasics();
    }

    private static void hashMapBasics() {
        Map<String, Integer> scores = new HashMap<>();
        scores.put("Asha", 90);
        scores.put("Ravi", 85);
        scores.put("Asha", 95);
        scores.putIfAbsent("Ravi", 99);

        System.out.println("HashMap scores: " + scores);
        System.out.println("get Asha: " + scores.get("Asha"));
        System.out.println("getOrDefault Meera: " + scores.getOrDefault("Meera", 0));
        System.out.println("containsKey Ravi: " + scores.containsKey("Ravi"));
        System.out.println("containsValue 95: " + scores.containsValue(95));

        for (Map.Entry<String, Integer> entry : scores.entrySet()) {
            System.out.println("entrySet iteration: " + entry.getKey() + " -> " + entry.getValue());
        }

        scores.replace("Ravi", 85, 88);
        scores.remove("Asha");
        System.out.println("After replace/remove: " + scores);
    }

    private static void computeAndMerge() {
        Map<String, List<String>> cityToUsers = new HashMap<>();
        cityToUsers.computeIfAbsent("Delhi", city -> new ArrayList<>()).add("Asha");
        cityToUsers.computeIfAbsent("Delhi", city -> new ArrayList<>()).add("Ravi");
        cityToUsers.computeIfAbsent("Mumbai", city -> new ArrayList<>()).add("Meera");
        System.out.println("computeIfAbsent grouping: " + cityToUsers);

        Map<String, Integer> wordCount = new HashMap<>();
        for (String word : List.of("java", "lld", "java", "map")) {
            wordCount.merge(word, 1, Integer::sum);
        }
        System.out.println("merge counter: " + wordCount);

        wordCount.computeIfPresent("map", (word, count) -> count + 10);
        wordCount.compute("new", (word, oldCount) -> oldCount == null ? 1 : oldCount + 1);
        System.out.println("compute variants: " + wordCount);
    }

    private static void linkedHashMapLru() {
        Map<String, String> lru = new LinkedHashMap<>(16, 0.75f, true) {
            protected boolean removeEldestEntry(Map.Entry<String, String> eldest) {
                return size() > 3;
            }
        };

        lru.put("A", "Apple");
        lru.put("B", "Ball");
        lru.put("C", "Cat");
        lru.get("A");
        lru.put("D", "Dog");

        System.out.println("LinkedHashMap access-order LRU: " + lru);
    }

    private static void treeMapNavigableOperations() {
        TreeMap<Integer, String> slots = new TreeMap<>();
        slots.put(900, "standup");
        slots.put(1100, "design review");
        slots.put(1500, "deep work");

        System.out.println("TreeMap slots: " + slots);
        System.out.println("firstKey: " + slots.firstKey());
        System.out.println("floorEntry(1000): " + slots.floorEntry(1000));
        System.out.println("ceilingEntry(1000): " + slots.ceilingEntry(1000));
        System.out.println("tailMap(1000): " + slots.tailMap(1000));

        Map<Integer, String> byReverseKey = new TreeMap<>(Comparator.reverseOrder());
        byReverseKey.putAll(slots);
        System.out.println("TreeMap custom comparator: " + byReverseKey);
    }

    private static void concurrentHashMapBasics() {
        ConcurrentHashMap<String, Integer> counts = new ConcurrentHashMap<>();
        counts.merge("success", 1, Integer::sum);
        counts.merge("success", 1, Integer::sum);
        counts.putIfAbsent("failure", 0);
        System.out.println("ConcurrentHashMap counts: " + counts);
    }
}

