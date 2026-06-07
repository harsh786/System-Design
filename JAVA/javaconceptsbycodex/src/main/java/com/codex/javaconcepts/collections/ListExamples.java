package com.codex.javaconcepts.collections;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.ListIterator;

public class ListExamples {
    public static void main(String[] args) {
        arrayListBasics();
        listIterationAndMutation();
        subListIsAView();
        arraysAsListAndListOf();
        linkedListAsListAndDeque();
    }

    private static void arrayListBasics() {
        List<String> names = new ArrayList<>();

        names.add("Asha");
        names.add("Ravi");
        names.add(1, "Meera");
        names.addAll(List.of("Zoya", "Kabir"));

        System.out.println("After add/addAll: " + names);
        System.out.println("get(0): " + names.get(0));
        System.out.println("contains Ravi: " + names.contains("Ravi"));
        System.out.println("indexOf Zoya: " + names.indexOf("Zoya"));

        String old = names.set(2, "Ira");
        System.out.println("set returned old value: " + old);
        System.out.println("After set: " + names);

        boolean removedByValue = names.remove("Asha");
        String removedByIndex = names.remove(0);
        System.out.println("remove(Object) removed? " + removedByValue);
        System.out.println("remove(index) removed: " + removedByIndex);
        System.out.println("After removals: " + names);

        names.sort(Comparator.naturalOrder());
        System.out.println("After sort: " + names);

        names.replaceAll(String::toUpperCase);
        System.out.println("After replaceAll: " + names);

        names.removeIf(name -> name.startsWith("Z"));
        System.out.println("After removeIf startsWith Z: " + names);
    }

    private static void listIterationAndMutation() {
        List<String> values = new ArrayList<>(List.of("keep-1", "remove-1", "keep-2"));

        Iterator<String> iterator = values.iterator();
        while (iterator.hasNext()) {
            String value = iterator.next();
            if (value.startsWith("remove")) {
                iterator.remove();
            }
        }

        ListIterator<String> listIterator = values.listIterator();
        while (listIterator.hasNext()) {
            String value = listIterator.next();
            if (value.equals("keep-2")) {
                listIterator.set("updated-2");
                listIterator.add("inserted-after-updated-2");
            }
        }

        System.out.println("Iterator/ListIterator result: " + values);
    }

    private static void subListIsAView() {
        List<String> letters = new ArrayList<>(List.of("A", "B", "C", "D"));
        List<String> middle = letters.subList(1, 3);
        middle.clear();
        System.out.println("subList clear changed original: " + letters);
    }

    private static void arraysAsListAndListOf() {
        List<String> fixedSize = Arrays.asList("A", "B");
        fixedSize.set(0, "X");
        System.out.println("Arrays.asList after set: " + fixedSize);

        List<String> immutable = List.of("A", "B");
        List<String> mutableCopy = new ArrayList<>(immutable);
        mutableCopy.add("C");
        System.out.println("Mutable copy of List.of: " + mutableCopy);

        List<Integer> numbers = new ArrayList<>(List.of(10, 20, 30));
        numbers.remove(1);
        numbers.remove(Integer.valueOf(10));
        System.out.println("remove overload example: " + numbers);
    }

    private static void linkedListAsListAndDeque() {
        LinkedList<String> linked = new LinkedList<>();
        linked.add("middle");
        linked.addFirst("first");
        linked.addLast("last");

        System.out.println("LinkedList as deque: " + linked);
        System.out.println("removeFirst: " + linked.removeFirst());
        System.out.println("removeLast: " + linked.removeLast());
        System.out.println("Remaining: " + linked);
    }
}

