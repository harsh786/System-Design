import java.util.*;

public class Problem25_DLLTextEditor {
    // LC 2296 style - cursor-based text editor
    static class Node{char c;Node prev,next;Node(char ch){c=ch;}}
    Node head=new Node('#'),tail=new Node('#'),cursor;
    
    Problem25_DLLTextEditor(){head.next=tail;tail.prev=head;cursor=head;}
    
    void addText(String text){for(char c:text.toCharArray()){Node n=new Node(c);n.next=cursor.next;n.prev=cursor;cursor.next.prev=n;cursor.next=n;cursor=n;}}
    int deleteText(int k){int d=0;while(k-->0&&cursor!=head){Node del=cursor;cursor=cursor.prev;cursor.next=del.next;del.next.prev=cursor;d++;}return d;}
    String cursorLeft(int k){while(k-->0&&cursor!=head)cursor=cursor.prev;return getLast10();}
    String cursorRight(int k){while(k-->0&&cursor.next!=tail)cursor=cursor.next;return getLast10();}
    String getLast10(){StringBuilder sb=new StringBuilder();Node n=cursor;int c=10;while(c-->0&&n!=head){sb.append(n.c);n=n.prev;}return sb.reverse().toString();}
    
    public static void main(String[] args) {
        Problem25_DLLTextEditor ed=new Problem25_DLLTextEditor();
        ed.addText("leetcode");
        System.out.println(ed.deleteText(4)); // 4
        ed.addText("practice");
        System.out.println(ed.cursorLeft(3)); // practi
        System.out.println(ed.cursorRight(2)); // practic
    }
}
