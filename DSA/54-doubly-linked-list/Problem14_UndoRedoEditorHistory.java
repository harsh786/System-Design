import java.util.*;

public class Problem14_UndoRedoEditorHistory {
    static class State { String text; State prev, next; State(String t){text=t;} }
    State cur;
    
    Problem14_UndoRedoEditorHistory(String init) { cur = new State(init); }
    void edit(String text) { State s=new State(text); cur.next=s; s.prev=cur; cur=s; }
    String undo() { if(cur.prev!=null) cur=cur.prev; return cur.text; }
    String redo() { if(cur.next!=null) cur=cur.next; return cur.text; }
    
    public static void main(String[] args) {
        Problem14_UndoRedoEditorHistory e = new Problem14_UndoRedoEditorHistory("hello");
        e.edit("hello world"); e.edit("hello world!");
        System.out.println(e.undo()); // hello world
        System.out.println(e.undo()); // hello
        System.out.println(e.redo()); // hello world
    }
}
