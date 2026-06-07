package com.codex.javaconcepts;

import com.codex.javaconcepts.collections.ListExamples;
import com.codex.javaconcepts.collections.MapExamples;
import com.codex.javaconcepts.collections.QueueExamples;
import com.codex.javaconcepts.collections.SetExamples;
import com.codex.javaconcepts.concurrency.ConcurrencyExamples;
import com.codex.javaconcepts.concurrency.ProducerConsumerBlockingQueue;
import com.codex.javaconcepts.core.CoreLanguageExamples;
import com.codex.javaconcepts.exceptions.ExceptionExamples;
import com.codex.javaconcepts.generics.GenericsExamples;
import com.codex.javaconcepts.jvm.JvmMemoryExamples;
import com.codex.javaconcepts.lld.MiniParkingLotExample;
import com.codex.javaconcepts.lld.ValueObjectExamples;
import com.codex.javaconcepts.oop.OopStaticInheritanceExamples;
import com.codex.javaconcepts.streams.StreamsExamples;

public class AllExamplesRunner {
    public static void main(String[] args) throws Exception {
        run("List", () -> ListExamples.main(args));
        run("Set", () -> SetExamples.main(args));
        run("Map", () -> MapExamples.main(args));
        run("Queue", () -> QueueExamples.main(args));
        run("OOP, static, inheritance", () -> OopStaticInheritanceExamples.main(args));
        run("Generics", () -> GenericsExamples.main(args));
        run("Streams", () -> StreamsExamples.main(args));
        run("Exceptions", () -> ExceptionExamples.main(args));
        run("Concurrency", () -> ConcurrencyExamples.main(args));
        run("Producer consumer", () -> ProducerConsumerBlockingQueue.main(args));
        run("JVM memory", () -> JvmMemoryExamples.main(args));
        run("Value objects", () -> ValueObjectExamples.main(args));
        run("Mini parking lot LLD", () -> MiniParkingLotExample.main(args));
        run("Core language", () -> CoreLanguageExamples.main(args));
    }

    private static void run(String title, Example example) throws Exception {
        System.out.println();
        System.out.println("========== " + title + " ==========");
        example.run();
    }

    @FunctionalInterface
    private interface Example {
        void run() throws Exception;
    }
}
