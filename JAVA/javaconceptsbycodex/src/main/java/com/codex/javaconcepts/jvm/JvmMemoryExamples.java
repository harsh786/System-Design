package com.codex.javaconcepts.jvm;

import java.util.ArrayList;
import java.util.List;

public class JvmMemoryExamples {
    public static void main(String[] args) {
        stackAndHeap();
        stringPool();
        runtimeMemory();
    }

    private static void stackAndHeap() {
        int localPrimitive = 10;
        User user = new User("u1", "asha@example.com");
        List<User> users = new ArrayList<>();
        users.add(user);

        System.out.println("Primitive local value: " + localPrimitive);
        System.out.println("Heap object through reference: " + users.get(0));
    }

    private static void stringPool() {
        String literalA = "java";
        String literalB = "java";
        String object = new String("java");

        System.out.println("literalA == literalB: " + (literalA == literalB));
        System.out.println("literalA == object: " + (literalA == object));
        System.out.println("literalA.equals(object): " + literalA.equals(object));
    }

    private static void runtimeMemory() {
        Runtime runtime = Runtime.getRuntime();
        long used = runtime.totalMemory() - runtime.freeMemory();
        System.out.println("Approx used heap bytes: " + used);
    }

    private record User(String id, String email) {
    }
}

