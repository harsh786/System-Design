import java.util.*;

public class Problem45_RangeIterator implements Iterator<Integer> {
    int current, end, step;

    public Problem45_RangeIterator(int start, int end, int step) {
        this.current = start; this.end = end; this.step = step;
    }

    public boolean hasNext() { return step > 0 ? current < end : current > end; }
    public Integer next() { int val = current; current += step; return val; }

    public static void main(String[] args) {
        Problem45_RangeIterator it = new Problem45_RangeIterator(0, 10, 2);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 0 2 4 6 8
        it = new Problem45_RangeIterator(10, 0, -3);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 10 7 4 1
    }
}
