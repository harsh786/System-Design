import java.util.*;

public class Problem38_CompressedRunLengthIterator implements Iterator<Character> {
    String data; int idx = 0;
    char currentChar; int currentCount;

    public Problem38_CompressedRunLengthIterator(String rle) {
        data = rle; advance();
    }

    void advance() {
        if (idx >= data.length()) { currentCount = 0; return; }
        currentChar = data.charAt(idx++);
        StringBuilder num = new StringBuilder();
        while (idx < data.length() && Character.isDigit(data.charAt(idx))) num.append(data.charAt(idx++));
        currentCount = num.length() > 0 ? Integer.parseInt(num.toString()) : 1;
    }

    public boolean hasNext() { return currentCount > 0; }
    public Character next() { currentCount--; if (currentCount == 0) advance(); return currentChar; }

    public static void main(String[] args) {
        Problem38_CompressedRunLengthIterator it = new Problem38_CompressedRunLengthIterator("a3b2c5");
        while (it.hasNext()) System.out.print(it.next());
        System.out.println(); // aaabbccccc
    }
}
