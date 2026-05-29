import java.util.*;

public class Problem46_ReverseIterator<T> implements Iterator<T> {
    List<T> list;
    int idx;

    public Problem46_ReverseIterator(List<T> list) { this.list = list; idx = list.size() - 1; }

    public boolean hasNext() { return idx >= 0; }
    public T next() { return list.get(idx--); }

    public static void main(String[] args) {
        Problem46_ReverseIterator<Integer> it = new Problem46_ReverseIterator<>(Arrays.asList(1,2,3,4,5));
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 5 4 3 2 1
    }
}
