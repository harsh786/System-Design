import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem44_PhaserBarrier {
    /**
     * Problem: Phaser Barrier
     * Multi-phase barrier using Java's Phaser.
     * Time: O(1) per arrival | Space: O(1)
     * Production Analogy: Multi-stage data pipeline where all workers sync between stages.
     */
    public static void main(String[] args) throws InterruptedException {
        Phaser phaser = new Phaser(3); // 3 parties
        for (int i = 0; i < 3; i++) {
            final int id = i;
            new Thread(() -> {
                for (int phase = 0; phase < 3; phase++) {
                    System.out.println("Thread " + id + " phase " + phase);
                    phaser.arriveAndAwaitAdvance();
                }
                phaser.arriveAndDeregister();
            }).start();
        }
        Thread.sleep(1000);
        System.out.println("All phases complete");
    }
}
