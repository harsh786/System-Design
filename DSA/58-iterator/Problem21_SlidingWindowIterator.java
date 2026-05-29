import java.util.*;

public class Problem21_SlidingWindowIterator implements Iterator<List<Integer>> {
    int[] arr; int windowSize, idx;

    public Problem21_SlidingWindowIterator(int[] arr, int windowSize) {
        this.arr = arr; this.windowSize = windowSize; idx = 0;
    }

    public boolean hasNext() { return idx + windowSize <= arr.length; }

    public List<Integer> next() {
        List<Integer> window = new ArrayList<>();
        for (int i = idx; i < idx + windowSize; i++) window.add(arr[i]);
        idx++;
        return window;
    }

    public static void main(String[] args) {
        Problem21_SlidingWindowIterator it = new Problem21_SlidingWindowIterator(new int[]{1,2,3,4,5}, 3);
        while (it.hasNext()) System.out.println(it.next());
    }
}
