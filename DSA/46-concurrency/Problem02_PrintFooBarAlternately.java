/**
 * Problem: Print FooBar Alternately
 * Two threads print "foo" and "bar" alternately n times.
 * 
 * Approach: Use Semaphores to alternate between two threads.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Request-response ping-pong between microservices,
 * or alternating read/write phases in a pipeline.
 */
import java.util.concurrent.*;

public class Problem02_PrintFooBarAlternately {
    private int n;
    private Semaphore fooSem = new Semaphore(1);
    private Semaphore barSem = new Semaphore(0);

    public Problem02_PrintFooBarAlternately(int n) { this.n = n; }

    public void foo(Runnable printFoo) throws InterruptedException {
        for (int i = 0; i < n; i++) {
            fooSem.acquire();
            printFoo.run();
            barSem.release();
        }
    }

    public void bar(Runnable printBar) throws InterruptedException {
        for (int i = 0; i < n; i++) {
            barSem.acquire();
            printBar.run();
            fooSem.release();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem02_PrintFooBarAlternately obj = new Problem02_PrintFooBarAlternately(3);
        Thread t1 = new Thread(() -> { try { obj.foo(() -> System.out.print("foo")); } catch (InterruptedException e) {} });
        Thread t2 = new Thread(() -> { try { obj.bar(() -> System.out.print("bar")); } catch (InterruptedException e) {} });
        t1.start(); t2.start();
        t1.join(); t2.join();
        System.out.println();
    }
}
