import java.util.*;

public class Problem05_Vector2DIterator implements Iterator<Integer> {
    int[][] vec;
    int outer, inner;

    public Problem05_Vector2DIterator(int[][] vec) { this.vec = vec; advance(); }

    void advance() { while (outer < vec.length && inner >= vec[outer].length) { outer++; inner = 0; } }

    public Integer next() { int val = vec[outer][inner++]; advance(); return val; }

    public boolean hasNext() { return outer < vec.length; }

    public static void main(String[] args) {
        int[][] vec = {{1,2},{3},{},{4,5,6}};
        Problem05_Vector2DIterator it = new Problem05_Vector2DIterator(vec);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
