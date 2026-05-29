/**
 * Problem: Print in Order
 * Three threads call first(), second(), third() - ensure execution order.
 * 
 * Approach: Use CountDownLatch or Semaphore to enforce ordering.
 * Time Complexity: O(1) per method
 * Space Complexity: O(1)
 * 
 * Production Analogy: Service initialization phases - DB connection must complete
 * before cache warming, which must complete before accepting traffic.
 */
import java.util.concurrent.*;

public class Problem01_PrintInOrder {
    private CountDownLatch latch1 = new CountDownLatch(1);
    private CountDownLatch latch2 = new CountDownLatch(1);

    public void first(Runnable printFirst) throws InterruptedException {
        printFirst.run();
        latch1.countDown();
    }

    public void second(Runnable printSecond) throws InterruptedException {
        latch1.await();
        printSecond.run();
        latch2.countDown();
    }

    public void third(Runnable printThird) throws InterruptedException {
        latch2.await();
        printThird.run();
    }

    public static void main(String[] args) throws InterruptedException {
        Problem01_PrintInOrder obj = new Problem01_PrintInOrder();
        Thread t3 = new Thread(() -> { try { obj.third(() -> System.out.print("third")); } catch (InterruptedException e) {} });
        Thread t2 = new Thread(() -> { try { obj.second(() -> System.out.print("second")); } catch (InterruptedException e) {} });
        Thread t1 = new Thread(() -> { try { obj.first(() -> System.out.print("first")); } catch (InterruptedException e) {} });
        t3.start(); t2.start(); t1.start();
        t3.join(); t2.join(); t1.join();
        System.out.println();
    }
}
