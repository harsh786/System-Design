import java.util.*;

public class Problem31_RateLimitedIterator implements Iterator<Integer> {
    Iterator<Integer> source;
    int ratePerSecond;
    long lastTime;
    int count;

    public Problem31_RateLimitedIterator(Iterator<Integer> source, int ratePerSecond) {
        this.source = source; this.ratePerSecond = ratePerSecond; lastTime = System.currentTimeMillis();
    }

    public boolean hasNext() { return source.hasNext(); }

    public Integer next() {
        count++;
        if (count >= ratePerSecond) {
            long elapsed = System.currentTimeMillis() - lastTime;
            if (elapsed < 1000) try { Thread.sleep(1000 - elapsed); } catch (InterruptedException e) {}
            lastTime = System.currentTimeMillis(); count = 0;
        }
        return source.next();
    }

    public static void main(String[] args) {
        Problem31_RateLimitedIterator it = new Problem31_RateLimitedIterator(
            Arrays.asList(1,2,3,4,5,6,7,8,9,10).iterator(), 100);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
