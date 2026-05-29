import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem41_TimerWheelScheduler {
    /**
     * Problem: Timer Wheel Scheduler
     * Hashed timing wheel for efficient timer management.
     * Approach: Circular array of buckets, each tick advances pointer.
     * Time: O(1) add/cancel, O(bucket_size) per tick | Space: O(n)
     * Production Analogy: Netty HashedWheelTimer for connection timeouts.
     */
    private final int wheelSize;
    private final List<List<Runnable>> wheel;
    private int currentTick = 0;

    public Problem41_TimerWheelScheduler(int wheelSize) {
        this.wheelSize = wheelSize;
        wheel = new ArrayList<>();
        for (int i = 0; i < wheelSize; i++) wheel.add(new ArrayList<>());
    }

    public void schedule(Runnable task, int ticksFromNow) {
        int slot = (currentTick + ticksFromNow) % wheelSize;
        synchronized (wheel.get(slot)) { wheel.get(slot).add(task); }
    }

    public void tick() {
        List<Runnable> tasks;
        synchronized (wheel.get(currentTick)) { tasks = new ArrayList<>(wheel.get(currentTick)); wheel.get(currentTick).clear(); }
        for (Runnable r : tasks) r.run();
        currentTick = (currentTick + 1) % wheelSize;
    }

    public static void main(String[] args) {
        Problem41_TimerWheelScheduler tw = new Problem41_TimerWheelScheduler(8);
        tw.schedule(() -> System.out.println("Fire at tick 3"), 3);
        tw.schedule(() -> System.out.println("Fire at tick 5"), 5);
        for (int i = 0; i < 8; i++) { System.out.println("Tick " + i); tw.tick(); }
    }
}
