/**
 * Personalization Dialog Component for AI customization
 */

import { Brain, RotateCcw, Save, Trash2 } from 'lucide-react';
import React, { useState, useEffect } from 'react';
import { Button } from './button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './dialog';
import { Input } from './input';
import { Label } from './label';
import { toast } from '../hooks/use-toast';
import {
  getUserSettings,
  updateCustomInstructions,
  clearUserMemory,
} from '../services/personalizationApi';

export function PersonalizationDialog({ open, onOpenChange }) {
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [instructions, setInstructions] = useState('');
  const [memoryCount, setMemoryCount] = useState(0);
  const [hasChanges, setHasChanges] = useState(false);
  const [originalInstructions, setOriginalInstructions] = useState('');

  // Load user settings when dialog opens
  useEffect(() => {
    if (open) {
      loadUserSettings();
    }
  }, [open]);

  // Track changes
  useEffect(() => {
    setHasChanges(instructions !== originalInstructions);
  }, [instructions, originalInstructions]);

  const loadUserSettings = async () => {
    setIsLoading(true);
    try {
      const settings = await getUserSettings();
      setInstructions(settings.custom_instructions || '');
      setOriginalInstructions(settings.custom_instructions || '');
      setMemoryCount(settings.memory_count || 0);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load personalization settings',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateCustomInstructions(instructions);
      setOriginalInstructions(instructions);
      toast({
        title: 'Success',
        description: 'Your AI personalization has been saved',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to save personalization settings',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearMemory = async () => {
    if (!window.confirm('Are you sure you want to clear all your learning history? This action cannot be undone.')) {
      return;
    }

    setIsClearing(true);
    try {
      await clearUserMemory();
      setMemoryCount(0);
      toast({
        title: 'Success',
        description: 'Your learning history has been cleared',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to clear learning history',
        variant: 'destructive',
      });
    } finally {
      setIsClearing(false);
    }
  };

  const handleReset = () => {
    setInstructions(originalInstructions);
  };

  const characterCount = instructions.length;
  const maxCharacters = 1500;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            Personalize Talimio
          </DialogTitle>
          <DialogDescription>
            Customize how AI responds to you based on your learning preferences and history.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="text-sm text-muted-foreground">Loading settings...</div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Custom Instructions Section */}
            <div className="space-y-3">
              <Label htmlFor="instructions" className="text-sm font-medium">
                Custom Instructions
              </Label>
              <div className="space-y-2">
                <textarea
                  id="instructions"
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Tell the AI how you'd like it to respond. For example: 'I prefer concise explanations with practical examples' or 'I'm a visual learner who likes diagrams and step-by-step guides.'"
                  className="w-full min-h-[120px] p-3 text-sm border border-input bg-background rounded-md resize-y focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                  maxLength={maxCharacters}
                />
                <div className="flex justify-between items-center text-xs text-muted-foreground">
                  <span>These instructions will be included in all AI interactions</span>
                  <span className={characterCount > maxCharacters * 0.9 ? 'text-warning' : ''}>
                    {characterCount}/{maxCharacters}
                  </span>
                </div>
              </div>
            </div>

            {/* Memory Statistics */}
            <div className="space-y-3">
              <Label className="text-sm font-medium">Learning History</Label>
              <div className="bg-muted/50 p-4 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{memoryCount} memories stored</p>
                    <p className="text-xs text-muted-foreground">
                      AI learns from your interactions to provide personalized responses
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleClearMemory}
                    disabled={isClearing || memoryCount === 0}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    {isClearing ? 'Clearing...' : 'Clear All'}
                  </Button>
                </div>
              </div>
            </div>

            {/* Privacy Notice */}
            <div className="bg-primary/5 border border-primary/20 p-4 rounded-lg">
              <h4 className="text-sm font-medium mb-2">Privacy & Data</h4>
              <ul className="text-xs text-muted-foreground space-y-1">
                <li>• Your data is stored locally and never shared with third parties</li>
                <li>• Memories are used only to improve your learning experience</li>
                <li>• You can export or delete your data at any time</li>
              </ul>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-between pt-4">
              <Button
                variant="outline"
                onClick={handleReset}
                disabled={!hasChanges || isSaving}
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                Reset
              </Button>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                  disabled={isSaving}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={!hasChanges || isSaving}
                >
                  <Save className="h-4 w-4 mr-2" />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}